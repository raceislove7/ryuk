"""Domain data contracts, not authorization or payment-execution interfaces.

Validate records at trust boundaries. Valid shape, a supplied digest, evidence text,
status, or ID does not establish authenticity, user consent, or provider success.
Services must reload canonical records and enforce current policy before acting.
"""

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
    model_validator,
)

NonEmptyString = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
# Zero is an explicit zero budget/price, never an unlimited or missing budget.
MinorUnits = Annotated[int, Field(strict=True, ge=0)]
PositiveInteger = Annotated[int, Field(strict=True, gt=0)]
Currency = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")]
ProposalDigest = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
Percentage = Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]
Confidence = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class DomainModel(BaseModel):
    """Reject misspelled or unexpected inputs rather than silently dropping them."""

    model_config = ConfigDict(extra="forbid", validate_default=True, allow_inf_nan=False)


class VerificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class CheckKind(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC = "SEMANTIC"


class PolicyOutcome(StrEnum):
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ALLOW_ELIGIBLE_FOR_CHECKOUT = "ALLOW_ELIGIBLE_FOR_CHECKOUT"


class PolicyReasonCode(StrEnum):
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    REQUIRED_ATTRIBUTE_FAILED = "REQUIRED_ATTRIBUTE_FAILED"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    APPROVAL_THRESHOLD_EXCEEDED = "APPROVAL_THRESHOLD_EXCEEDED"
    INTENT_REVIEW_REQUIRED = "INTENT_REVIEW_REQUIRED"
    MERCHANT_REVIEW_REQUIRED = "MERCHANT_REVIEW_REQUIRED"
    DUPLICATE_ATTEMPT = "DUPLICATE_ATTEMPT"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    PROPOSAL_CHANGED = "PROPOSAL_CHANGED"
    VERIFICATION_INVALID = "VERIFICATION_INVALID"
    PAYMENT_STATE_UNKNOWN = "PAYMENT_STATE_UNKNOWN"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_INVALID = "APPROVAL_INVALID"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class ApprovalState(StrEnum):
    """Application approval state; never substitutes for PayPal buyer approval."""

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class PaymentState(StrEnum):
    """Payment vocabulary enforced by the centralized state-machine service."""

    CREATED = "CREATED"
    POLICY_CHECK = "POLICY_CHECK"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    CHECKOUT_READY = "CHECKOUT_READY"
    AWAITING_PAYPAL_BUYER = "AWAITING_PAYPAL_BUYER"
    CAPTURE_PENDING = "CAPTURE_PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PENDING_PROVIDER = "PENDING_PROVIDER"


class RequirementSource(DomainModel):
    """Exact validated source association; offsets count Unicode code points, not UTF-16."""

    role: Literal["required", "preferred"]
    name: NonEmptyString
    quote: NonEmptyString
    start: Annotated[int, Field(strict=True, ge=0)]
    end: Annotated[int, Field(strict=True, gt=0)]


class PurchaseIntent(DomainModel):
    category: NonEmptyString
    query: NonEmptyString
    currency: Currency
    budget_max_minor: MinorUnits
    approval_threshold_minor: MinorUnits
    required_attributes: dict[NonEmptyString, JsonValue] = Field(default_factory=dict)
    preferred_attributes: dict[NonEmptyString, JsonValue] = Field(default_factory=dict)
    quantity: PositiveInteger = 1
    notes: str | None = None
    requirement_sources: list[RequirementSource] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_legacy_compatible(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = handler(self)
        # Preserve old snapshot/digest bytes for persisted quote-less intents.
        if not self.requirement_sources:
            data.pop("requirement_sources", None)
        return data

    @model_validator(mode="after")
    def validate_threshold(self) -> Self:
        """An approval threshold cannot raise the hard budget ceiling."""
        if self.approval_threshold_minor > self.budget_max_minor:
            raise ValueError("approval_threshold_minor must not exceed budget_max_minor")
        if self.required_attributes.keys() & self.preferred_attributes.keys():
            raise ValueError("an attribute cannot be both required and preferred")
        if self.requirement_sources:
            expected = {
                (role, name)
                for role, values in (
                    ("required", self.required_attributes),
                    ("preferred", self.preferred_attributes),
                )
                for name in values
            }
            actual = set()
            for source in self.requirement_sources:
                key = (source.role, source.name)
                if key in actual or key not in expected:
                    raise ValueError("Source association must match one distinct requirement")
                if (
                    source.end <= source.start
                    or source.end > len(self.query)
                    or self.query.count(source.quote) != 1
                    or self.query[source.start : source.end] != source.quote
                ):
                    raise ValueError("Source quote must identify its exact unique request span")
                actual.add(key)
            if actual != expected:
                raise ValueError("Source associations must cover every parsed requirement")
        return self


class Offer(DomainModel):
    offer_id: NonEmptyString
    merchant_id: NonEmptyString
    title: NonEmptyString
    amount_minor: MinorUnits
    currency: Currency
    attributes: dict[NonEmptyString, JsonValue] = Field(default_factory=dict)
    # Per-attribute supporting excerpts or source references; absent evidence is valid input.
    evidence: dict[NonEmptyString, list[NonEmptyString]] = Field(default_factory=dict)
    source: NonEmptyString


class CheckResult(DomainModel):
    requirement: NonEmptyString
    status: VerificationStatus
    kind: CheckKind = CheckKind.DETERMINISTIC
    evidence: list[NonEmptyString] = Field(default_factory=list)
    confidence: Confidence | None = None
    explanation: NonEmptyString

    @model_validator(mode="after")
    def validate_semantic_evidence(self) -> Self:
        """A semantic PASS must include evidence, regardless of confidence."""
        if self.kind == CheckKind.SEMANTIC and self.status == VerificationStatus.PASS:
            if not self.evidence:
                raise ValueError("semantic PASS requires evidence")
        return self


class VerificationResult(DomainModel):
    verification_snapshot_id: NonEmptyString
    offer_id: NonEmptyString
    status: VerificationStatus
    required_checks: list[CheckResult]
    preferred_checks: list[CheckResult] = Field(default_factory=list)
    preference_score: Percentage
    # Missing evidence for mandatory requirements; preferences do not block PASS.
    missing_evidence: list[NonEmptyString] = Field(default_factory=list)
    explanation: NonEmptyString

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        """Reject summaries contradicting their supplied checks; do not run checks."""
        requirements = [check.requirement for check in self.required_checks]
        if len(requirements) != len(set(requirements)):
            raise ValueError("required_checks must contain unique requirements")
        preferences = [check.requirement for check in self.preferred_checks]
        if len(preferences) != len(set(preferences)):
            raise ValueError("preferred_checks must contain unique requirements")
        if set(requirements) & set(preferences):
            raise ValueError("a check cannot be both required and preferred")
        statuses = {check.status for check in self.required_checks}
        if VerificationStatus.FAIL in statuses:
            expected = VerificationStatus.FAIL
        elif not statuses or VerificationStatus.UNKNOWN in statuses or self.missing_evidence:
            expected = VerificationStatus.UNKNOWN
        else:
            expected = VerificationStatus.PASS
        if self.status != expected:
            raise ValueError("verification status contradicts required checks or missing evidence")
        return self


class PolicyDecision(DomainModel):
    decision: PolicyOutcome
    reason_codes: list[PolicyReasonCode] = Field(default_factory=list)
    amount_minor: MinorUnits
    currency: Currency
    budget_remaining_minor: MinorUnits
    # Explicit because denied offer currency can differ from the budget currency.
    budget_currency: Currency | None = None
    policy_version: NonEmptyString

    @model_validator(mode="after")
    def validate_reasons(self) -> Self:
        """Denial and escalation need an explanation; rules are evaluated later."""
        if self.decision != PolicyOutcome.ALLOW_ELIGIBLE_FOR_CHECKOUT and not self.reason_codes:
            raise ValueError("DENY and REQUIRE_APPROVAL require reason_codes")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason_codes must be unique")
        return self


class PurchaseProposal(DomainModel):
    proposal_id: NonEmptyString
    user_id: NonEmptyString
    intent: PurchaseIntent
    offer: Offer
    policy_version: NonEmptyString
    created_at: AwareDatetime
    verification: VerificationResult | None = None
    policy_decision: PolicyDecision | None = None
    proposal_digest: ProposalDigest | None = None
    # Set only by trusted orchestration; no browser or model DTO accepts this flag.
    intent_review_required: Annotated[bool, Field(strict=True)] = False

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        """Allow unsafe offers to be represented, but reject mismatched snapshots."""
        if self.verification and self.verification.offer_id != self.offer.offer_id:
            raise ValueError("verification must refer to the selected offer")
        if self.policy_decision:
            decision = self.policy_decision
            if (decision.amount_minor, decision.currency, decision.policy_version) != (
                self.offer.amount_minor,
                self.offer.currency,
                self.policy_version,
            ):
                raise ValueError("policy decision must match offer terms and policy version")
        return self


class ProposalBinding(DomainModel):
    """Explicit canonical references, not proof that a supplied binding is trusted."""

    proposal_id: NonEmptyString
    user_id: NonEmptyString
    offer_id: NonEmptyString
    merchant_id: NonEmptyString
    amount_minor: MinorUnits
    currency: Currency
    policy_version: NonEmptyString
    verification_snapshot_id: NonEmptyString
    proposal_digest: ProposalDigest


class ApprovalRequest(ProposalBinding):
    approval_request_id: NonEmptyString
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: AwareDatetime
    expires_at: AwareDatetime
    decided_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_times(self) -> Self:
        """Validate historical timestamps, not current approval authorization."""
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        decided = self.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED)
        if decided:
            if self.decided_at is None:
                raise ValueError("approved or rejected requests require decided_at")
            if not self.created_at <= self.decided_at < self.expires_at:
                raise ValueError("decided_at must be within the approval window")
        elif self.status == ApprovalStatus.PENDING and self.decided_at is not None:
            raise ValueError("pending requests must not have decided_at")
        elif self.decided_at is not None:
            if not self.created_at <= self.decided_at < self.expires_at:
                raise ValueError("decided_at must be within the approval window")
        return self


class PaymentIntent(ProposalBinding):
    payment_intent_id: NonEmptyString
    idempotency_key: NonEmptyString
    created_at: AwareDatetime
    state: PaymentState = PaymentState.CREATED
    approval_state: ApprovalState = ApprovalState.PENDING
    approval_request_id: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_approval_reference(self) -> Self:
        """An approved application state needs a reference, not a fabricated flag."""
        referenced_states = {
            ApprovalState.APPROVED,
            ApprovalState.REJECTED,
            ApprovalState.EXPIRED,
            ApprovalState.INVALIDATED,
        }
        if self.approval_state in referenced_states and self.approval_request_id is None:
            raise ValueError(
                "decided, expired, or invalidated approval state requires approval_request_id"
            )
        if (
            self.approval_state == ApprovalState.NOT_REQUIRED
            and self.approval_request_id is not None
        ):
            raise ValueError("NOT_REQUIRED must not reference an approval request")
        return self
