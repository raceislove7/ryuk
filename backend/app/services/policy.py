"""Pure deterministic financial eligibility; no LLM, I/O, clocks, or side effects.

All authority records must be loaded by trusted backend code. This function is not
an API accepting browser/model policy limits, approvals, or payment-history flags.
"""

from datetime import datetime

from pydantic import AwareDatetime, TypeAdapter

from app.schemas import (
    ApprovalRequest,
    ApprovalStatus,
    PolicyDecision,
    PolicyOutcome,
    PolicyReasonCode,
    PurchaseProposal,
    VerificationStatus,
)
from app.schemas.policy import AttemptSnapshot, AttemptState, BudgetSnapshot, FinancialPolicy
from app.services.proposal_binding import InvalidProposalBinding, require_proposal_binding
from app.services.verifier import verify_offer


class InvalidPolicyContext(ValueError):
    """Mismatched authority records or evaluation time; stop without eligibility."""


def evaluate_policy(
    proposal: PurchaseProposal,
    policy: FinancialPolicy,
    budget: BudgetSnapshot,
    attempts: AttemptSnapshot,
    *,
    evaluated_at: datetime,
    approval: ApprovalRequest | None = None,
) -> PolicyDecision:
    """Return eligibility from current records, with DENY taking precedence.

    No reservation, duplicate lock, approval transition, digest generation, or
    capture occurs. ALLOW_ELIGIBLE_FOR_CHECKOUT still requires all later checkout
    gates, including canonical digest revalidation and PayPal buyer approval.
    """
    proposal = PurchaseProposal.model_validate(proposal.model_dump(warnings=False))
    policy = FinancialPolicy.model_validate(policy.model_dump(warnings=False))
    budget = BudgetSnapshot.model_validate(budget.model_dump(warnings=False))
    attempts = AttemptSnapshot.model_validate(attempts.model_dump(warnings=False))
    now = TypeAdapter(AwareDatetime).validate_python(evaluated_at, strict=True)
    if approval is not None:
        approval = ApprovalRequest.model_validate(approval.model_dump(warnings=False))
    if not (
        proposal.user_id == policy.user_id == budget.user_id == attempts.user_id
        and attempts.proposal_id == proposal.proposal_id
        and budget.currency == policy.currency
        and now >= proposal.created_at
    ):
        raise InvalidPolicyContext("Policy context ownership, budget currency, or time is invalid.")

    hard: list[PolicyReasonCode] = []
    review: list[PolicyReasonCode] = []
    intent, offer = proposal.intent, proposal.offer
    if proposal.intent_review_required:
        review.append(PolicyReasonCode.INTENT_REVIEW_REQUIRED)
    remaining = budget.remaining_minor
    if proposal.policy_version != policy.version:
        hard.append(PolicyReasonCode.PROPOSAL_CHANGED)
    same_currency = offer.currency == intent.currency == policy.currency
    if not same_currency:
        hard.append(PolicyReasonCode.CURRENCY_MISMATCH)
    else:
        ceiling = min(intent.budget_max_minor, policy.max_amount_minor, remaining)
        if (
            offer.amount_minor > ceiling
            or budget.settled_minor + budget.reserved_minor > budget.limit_minor
        ):
            hard.append(PolicyReasonCode.BUDGET_EXCEEDED)
        threshold = min(intent.approval_threshold_minor, policy.approval_threshold_minor)
        if offer.amount_minor > threshold:
            review.append(PolicyReasonCode.APPROVAL_THRESHOLD_EXCEEDED)

    # Recompute the current deterministic result; a supplied PASS is not authority.
    current = verify_offer(intent, offer)
    if current.status == VerificationStatus.FAIL:
        hard.append(PolicyReasonCode.REQUIRED_ATTRIBUTE_FAILED)
    elif current.status == VerificationStatus.UNKNOWN:
        review.append(PolicyReasonCode.MISSING_EVIDENCE)
    if proposal.verification is None:
        review.append(PolicyReasonCode.MISSING_EVIDENCE)
    elif proposal.verification != current:
        hard.append(PolicyReasonCode.VERIFICATION_INVALID)
    if proposal.proposal_digest is not None:
        try:
            require_proposal_binding(proposal)
        except InvalidProposalBinding:
            hard.append(PolicyReasonCode.PROPOSAL_CHANGED)

    # Quantity is separate from explicit attribute maps in the current verifier.
    quantity_key = "rooms" if intent.category.strip().casefold() == "hotel" else "quantity"
    actual_quantity = offer.attributes.get(quantity_key)
    if type(actual_quantity) is not int or actual_quantity < 1:
        review.append(PolicyReasonCode.MISSING_EVIDENCE)
    elif actual_quantity != intent.quantity:
        hard.append(PolicyReasonCode.REQUIRED_ATTRIBUTE_FAILED)
    elif not offer.evidence.get(quantity_key):
        review.append(PolicyReasonCode.MISSING_EVIDENCE)
    if offer.merchant_id not in policy.allowed_merchant_ids:
        review.append(PolicyReasonCode.MERCHANT_REVIEW_REQUIRED)
    if attempts.state == AttemptState.DUPLICATE:
        hard.append(PolicyReasonCode.DUPLICATE_ATTEMPT)
    elif attempts.state == AttemptState.UNKNOWN:
        hard.append(PolicyReasonCode.PAYMENT_STATE_UNKNOWN)

    approved = False
    if approval is not None:
        binding = {
            "user_id": proposal.user_id,
            "proposal_id": proposal.proposal_id,
            "offer_id": offer.offer_id,
            "merchant_id": offer.merchant_id,
            "amount_minor": offer.amount_minor,
            "currency": offer.currency,
            "policy_version": policy.version,
            "verification_snapshot_id": (
                proposal.verification.verification_snapshot_id if proposal.verification else None
            ),
            "proposal_digest": proposal.proposal_digest,
        }
        same_binding = all(getattr(approval, key) == value for key, value in binding.items())
        if not same_binding:
            hard.append(PolicyReasonCode.PROPOSAL_CHANGED)
        if (
            approval.created_at < proposal.created_at
            or approval.created_at > now
            or (approval.decided_at is not None and approval.decided_at > now)
        ):
            hard.append(PolicyReasonCode.APPROVAL_INVALID)
        if approval.status == ApprovalStatus.INVALIDATED:
            hard.append(PolicyReasonCode.PROPOSAL_CHANGED)
        elif approval.status == ApprovalStatus.REJECTED:
            hard.append(PolicyReasonCode.APPROVAL_REJECTED)
        elif approval.status == ApprovalStatus.EXPIRED or now >= approval.expires_at:
            review.append(PolicyReasonCode.APPROVAL_EXPIRED)
        elif approval.status == ApprovalStatus.PENDING:
            review.append(PolicyReasonCode.APPROVAL_PENDING)
        elif same_binding and approval.status == ApprovalStatus.APPROVED:
            approved = True

    if hard:
        outcome = PolicyOutcome.DENY
        reasons = hard + review
    elif review and not approved:
        outcome = PolicyOutcome.REQUIRE_APPROVAL
        reasons = review
    else:
        outcome = PolicyOutcome.ALLOW_ELIGIBLE_FOR_CHECKOUT
        reasons = [PolicyReasonCode.APPROVAL_GRANTED] if approved else []
    # Stable enum order, unique reason codes; no dependence on set iteration order.
    codes = [code for code in PolicyReasonCode if code in reasons]
    return PolicyDecision(
        decision=outcome,
        reason_codes=codes,
        amount_minor=offer.amount_minor,
        currency=offer.currency,
        budget_remaining_minor=remaining,
        budget_currency=budget.currency,
        policy_version=policy.version,
    )
