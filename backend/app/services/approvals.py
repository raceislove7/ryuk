"""Internal in-memory approval workflow, with canonical records and fail-closed restart.

Not an authentication provider, durable database, public API, or payment executor.
Only trusted backend code may register proposals or supply an authenticated actor ID.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import RLock
from uuid import uuid4

from pydantic import AwareDatetime, TypeAdapter

from app.schemas import (
    ApprovalRequest,
    ApprovalStatus,
    PolicyDecision,
    PolicyOutcome,
    PurchaseProposal,
)
from app.schemas.domain import NonEmptyString
from app.schemas.policy import AttemptSnapshot, BudgetSnapshot, FinancialPolicy
from app.services.policy import evaluate_policy
from app.services.proposal_binding import (
    InvalidProposalBinding,
    bind_proposal,
    require_proposal_binding,
)

DEFAULT_APPROVAL_TTL = timedelta(minutes=10)
MAX_APPROVAL_TTL = timedelta(hours=1)


class ApprovalAccessError(PermissionError):
    """The authenticated caller does not own the requested record."""


class ApprovalStateError(RuntimeError):
    """Missing, superseded, expired, invalidated, or already decided approval."""


class ProposalConflictError(RuntimeError):
    """Canonical proposal changed since the backend caller loaded it."""


class ApprovalPolicyError(RuntimeError):
    """Policy blocks this operation; the backend may inspect the safe typed decision."""

    def __init__(self, decision: PolicyDecision) -> None:
        super().__init__("Current financial policy does not permit this approval.")
        self.decision = decision.model_copy(deep=True)


class InMemoryApprovalService:
    """Own canonical proposal/request copies and serialize workflow updates in one process."""

    def __init__(self, *, ttl: timedelta = DEFAULT_APPROVAL_TTL) -> None:
        if not isinstance(ttl, timedelta) or not timedelta(0) < ttl <= MAX_APPROVAL_TTL:
            raise ValueError("Approval TTL must be positive and at most one hour.")
        self._ttl = ttl
        self._lock = RLock()
        self._proposals: dict[str, PurchaseProposal] = {}
        self._requests: dict[str, ApprovalRequest] = {}
        self._current: dict[str, str] = {}
        self._last_seen: dict[str, datetime] = {}

    def register_proposal(
        self, proposal: PurchaseProposal, *, at: datetime, expected_digest: str | None = None
    ) -> PurchaseProposal:
        """Backend-only canonical write; changed bindings permanently revoke prior grants.

        Changed updates require the previous digest, preventing stale overwrites. Same
        content may be registered idempotently. Returned records are always copies.
        """
        bound = bind_proposal(proposal)
        now = TypeAdapter(AwareDatetime).validate_python(at, strict=True)
        if now < bound.created_at:
            raise ValueError("Cannot register a future-dated proposal.")
        with self._lock:
            old = self._proposals.get(bound.proposal_id)
            if old is not None and old.proposal_digest != bound.proposal_digest:
                if expected_digest != old.proposal_digest:
                    raise ProposalConflictError(
                        "Canonical proposal changed; reload before updating."
                    )
            self._observe(bound.proposal_id, now)
            if old is not None and old.proposal_digest != bound.proposal_digest:
                self._invalidate(bound.proposal_id)
            self._proposals[bound.proposal_id] = bound
            return bound.model_copy(deep=True)

    def get_proposal(self, proposal_id: str, *, actor_user_id: str) -> PurchaseProposal:
        """Read the owned canonical proposal without exposing mutable stored records."""
        with self._lock:
            return self._proposal(proposal_id, actor_user_id).model_copy(deep=True)

    def get_request(self, request_id: str, *, actor_user_id: str, at: datetime) -> ApprovalRequest:
        """Read owned history and persist expiry; invalidated records never become active again."""
        with self._lock:
            request = self._request(request_id, actor_user_id)
            now = self._observe(request.proposal_id, at)
            return self._expire(request, now).model_copy(deep=True)

    def create_request(
        self,
        proposal_id: str,
        *,
        actor_user_id: str,
        at: datetime,
        policy: FinancialPolicy,
        budget: BudgetSnapshot,
        attempts: AttemptSnapshot,
    ) -> ApprovalRequest:
        """Create PENDING only for a currently policy-permitted canonical proposal."""
        with self._lock:
            proposal = self._proposal(proposal_id, actor_user_id)
            now = self._observe(proposal_id, at)
            require_proposal_binding(proposal)
            decision = evaluate_policy(proposal, policy, budget, attempts, evaluated_at=now)
            if decision.decision == PolicyOutcome.DENY:
                if policy.version != proposal.policy_version:
                    self._invalidate(proposal_id)
                raise ApprovalPolicyError(decision)
            current_id = self._current.get(proposal_id)
            if current_id is not None:
                current = self._refresh(self._requests[current_id], proposal, now)
                if current.status == ApprovalStatus.PENDING:
                    return current.model_copy(deep=True)  # Retries do not extend consent TTL.
            self._invalidate(proposal_id)  # A new review supersedes any previous grant.
            request = ApprovalRequest(
                approval_request_id=str(uuid4()),
                proposal_id=proposal.proposal_id,
                user_id=proposal.user_id,
                offer_id=proposal.offer.offer_id,
                merchant_id=proposal.offer.merchant_id,
                amount_minor=proposal.offer.amount_minor,
                currency=proposal.offer.currency,
                policy_version=proposal.policy_version,
                verification_snapshot_id=proposal.verification.verification_snapshot_id,
                proposal_digest=proposal.proposal_digest,
                created_at=now,
                expires_at=now + self._ttl,
            )
            self._requests[request.approval_request_id] = request
            self._current[proposal_id] = request.approval_request_id
            return request.model_copy(deep=True)

    def approve_request(
        self,
        request_id: str,
        *,
        actor_user_id: str,
        at: datetime,
        policy: FinancialPolicy,
        budget: BudgetSnapshot,
        attempts: AttemptSnapshot,
    ) -> ApprovalRequest:
        """Record buyer consent once, only after current binding/time/policy revalidation."""
        with self._lock:
            request, proposal, now = self._pending(request_id, actor_user_id, at)
            decision = evaluate_policy(proposal, policy, budget, attempts, evaluated_at=now)
            if decision.decision == PolicyOutcome.DENY:
                if policy.version != proposal.policy_version:
                    self._invalidate(proposal.proposal_id)
                raise ApprovalPolicyError(decision)
            data = request.model_dump() | {"status": ApprovalStatus.APPROVED, "decided_at": now}
            approved = ApprovalRequest.model_validate(data)
            decision = evaluate_policy(
                proposal, policy, budget, attempts, evaluated_at=now, approval=approved
            )
            if decision.decision != PolicyOutcome.ALLOW_ELIGIBLE_FOR_CHECKOUT:
                raise ApprovalPolicyError(decision)
            self._requests[request_id] = approved
            return approved.model_copy(deep=True)

    def reject_request(
        self, request_id: str, *, actor_user_id: str, at: datetime
    ) -> ApprovalRequest:
        """Buyer rejection needs ownership/binding/time validation, not spending eligibility."""
        with self._lock:
            request, _, now = self._pending(request_id, actor_user_id, at)
            rejected = ApprovalRequest.model_validate(
                request.model_dump() | {"status": ApprovalStatus.REJECTED, "decided_at": now}
            )
            self._requests[request_id] = rejected
            return rejected.model_copy(deep=True)

    def revalidate_for_checkout(
        self,
        proposal_id: str,
        *,
        actor_user_id: str,
        at: datetime,
        policy: FinancialPolicy,
        budget: BudgetSnapshot,
        attempts: AttemptSnapshot,
        approval_request_id: str | None = None,
    ) -> PolicyDecision:
        """Reload owned records and rerun current policy; ignoring a request cannot bypass it."""
        with self._lock:
            proposal = self._proposal(proposal_id, actor_user_id)
            now = self._observe(proposal_id, at)
            try:
                require_proposal_binding(proposal)
            except InvalidProposalBinding:
                self._invalidate(proposal_id)
                raise
            current_id = self._current.get(proposal_id)
            if approval_request_id is not None and approval_request_id != current_id:
                raise ApprovalStateError(
                    "This approval is not the current request for the proposal."
                )
            request = None
            if current_id is not None:
                request = self._refresh(self._requests[current_id], proposal, now)
                if policy.version != proposal.policy_version:
                    self._invalidate(proposal_id)
                    request = self._requests[current_id]
            return evaluate_policy(
                proposal, policy, budget, attempts, evaluated_at=now, approval=request
            )

    @contextmanager
    def checkout_guard(
        self,
        proposal_id: str,
        *,
        actor_user_id: str,
        at: datetime,
        policy: FinancialPolicy,
        budget: BudgetSnapshot,
        attempts: AttemptSnapshot,
        approval_request_id: str | None = None,
    ) -> Iterator[tuple[PurchaseProposal, ApprovalRequest | None]]:
        """Hold canonical consent stable through a synchronous reservation/dispatch claim.

        Never await inside this guard. Callers acquire their ledger transaction first.
        It is not a distributed approval lock; lost authority fails closed on restart.
        """
        with self._lock:
            decision = self.revalidate_for_checkout(
                proposal_id,
                actor_user_id=actor_user_id,
                at=at,
                policy=policy,
                budget=budget,
                attempts=attempts,
                approval_request_id=approval_request_id,
            )
            if decision.decision != PolicyOutcome.ALLOW_ELIGIBLE_FOR_CHECKOUT:
                raise ApprovalPolicyError(decision)
            proposal = self._proposal(proposal_id, actor_user_id)
            current_id = self._current.get(proposal_id)
            request = self._requests.get(current_id) if current_id is not None else None
            yield (
                proposal.model_copy(deep=True),
                request.model_copy(deep=True) if request is not None else None,
            )

    def _proposal(self, proposal_id: str, actor_user_id: str) -> PurchaseProposal:
        actor = TypeAdapter(NonEmptyString).validate_python(actor_user_id)
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.user_id != actor:
            raise ApprovalAccessError("Proposal not found or access denied.")
        return proposal

    def _request(self, request_id: str, actor_user_id: str) -> ApprovalRequest:
        actor = TypeAdapter(NonEmptyString).validate_python(actor_user_id)
        request = self._requests.get(request_id)
        if request is None or request.user_id != actor:
            raise ApprovalAccessError("Approval not found or access denied.")
        return request

    def _observe(self, proposal_id: str, at: datetime) -> datetime:
        now = TypeAdapter(AwareDatetime).validate_python(at, strict=True)
        if proposal_id in self._last_seen and now < self._last_seen[proposal_id]:
            raise ValueError("Approval workflow time must not move backwards.")
        self._last_seen[proposal_id] = now
        return now

    def _invalidate(self, proposal_id: str) -> None:
        for request_id, request in self._requests.items():
            if request.proposal_id == proposal_id and request.status in (
                ApprovalStatus.PENDING,
                ApprovalStatus.APPROVED,
            ):
                self._requests[request_id] = ApprovalRequest.model_validate(
                    request.model_dump() | {"status": ApprovalStatus.INVALIDATED}
                )

    def _expire(self, request: ApprovalRequest, now: datetime) -> ApprovalRequest:
        if (
            request.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED)
            and now >= request.expires_at
        ):
            request = ApprovalRequest.model_validate(
                request.model_dump() | {"status": ApprovalStatus.EXPIRED}
            )
            self._requests[request.approval_request_id] = request
        return request

    def _refresh(
        self, request: ApprovalRequest, proposal: PurchaseProposal, now: datetime
    ) -> ApprovalRequest:
        try:
            require_proposal_binding(proposal)
        except InvalidProposalBinding:
            self._invalidate(proposal.proposal_id)
            raise
        terms = {
            "user_id": proposal.user_id,
            "proposal_id": proposal.proposal_id,
            "offer_id": proposal.offer.offer_id,
            "merchant_id": proposal.offer.merchant_id,
            "amount_minor": proposal.offer.amount_minor,
            "currency": proposal.offer.currency,
            "policy_version": proposal.policy_version,
            "verification_snapshot_id": proposal.verification.verification_snapshot_id,
            "proposal_digest": proposal.proposal_digest,
        }
        if any(getattr(request, key) != value for key, value in terms.items()):
            self._invalidate(proposal.proposal_id)
            request = self._requests[request.approval_request_id]
        return self._expire(request, now)

    def _pending(
        self, request_id: str, actor_user_id: str, at: datetime
    ) -> tuple[ApprovalRequest, PurchaseProposal, datetime]:
        request = self._request(request_id, actor_user_id)
        proposal = self._proposal(request.proposal_id, actor_user_id)
        now = self._observe(proposal.proposal_id, at)
        request = self._refresh(request, proposal, now)
        if self._current.get(proposal.proposal_id) != request_id:
            raise ApprovalStateError("This approval request was superseded.")
        if request.status != ApprovalStatus.PENDING:
            raise ApprovalStateError("Only a current, unexpired PENDING request can be decided.")
        return request, proposal, now
