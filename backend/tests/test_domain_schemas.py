"""Contract tests for untrusted JSON and internally linked domain records."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import (
    ApprovalRequest,
    ApprovalState,
    ApprovalStatus,
    CheckResult,
    Offer,
    PaymentIntent,
    PaymentState,
    PolicyDecision,
    PurchaseIntent,
    PurchaseProposal,
    VerificationResult,
    VerificationStatus,
)

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
BINDING = {
    "proposal_id": "proposal-1",
    "user_id": "user-1",
    "offer_id": "hotel-1",
    "merchant_id": "merchant-1",
    "amount_minor": 118_000,
    "currency": "USD",
    "policy_version": "policy-v1",
    "verification_snapshot_id": "snapshot-1",
    "proposal_digest": "a" * 64,
}
MODELS = {
    "intent": PurchaseIntent,
    "offer": Offer,
    "check": CheckResult,
    "verification": VerificationResult,
    "policy": PolicyDecision,
    "proposal": PurchaseProposal,
    "approval": ApprovalRequest,
    "payment": PaymentIntent,
}
MONEY_FIELDS = [
    ("intent", "budget_max_minor"),
    ("intent", "approval_threshold_minor"),
    ("offer", "amount_minor"),
    ("policy", "amount_minor"),
    ("policy", "budget_remaining_minor"),
    ("approval", "amount_minor"),
    ("payment", "amount_minor"),
]


@pytest.fixture
def records() -> dict[str, dict[str, Any]]:
    """A complete hotel proposal with explicit monetary and snapshot bindings."""
    intent = {
        "category": "hotel", "query": "Five nights with a gym",
        "currency": "USD", "budget_max_minor": 150_000,
        "approval_threshold_minor": 130_000,
        "required_attributes": {"gym": True},
        "preferred_attributes": {"private_pool": True},
    }
    offer = {
        "offer_id": "hotel-1", "merchant_id": "merchant-1", "title": "Synthetic hotel",
        "amount_minor": 118_000, "currency": "USD", "attributes": {"gym": True},
        "evidence": {"gym": ["Synthetic amenity record: gym available"]},
        "source": "synthetic fixture",
    }
    check = {
        "requirement": "gym", "status": "PASS", "kind": "SEMANTIC",
        "evidence": ["Synthetic amenity record: gym available"],
        "confidence": 0.9, "explanation": "The supplied evidence supports gym access.",
    }
    verification = {
        "verification_snapshot_id": "snapshot-1", "offer_id": "hotel-1", "status": "PASS",
        "required_checks": [check], "preference_score": 92,
        "explanation": "Mandatory gym requirement verified.",
    }
    policy = {
        "decision": "ALLOW_ELIGIBLE_FOR_CHECKOUT", "amount_minor": 118_000,
        "currency": "USD", "budget_remaining_minor": 150_000, "policy_version": "policy-v1",
    }
    return deepcopy({
        "intent": intent, "offer": offer, "check": check,
        "verification": verification, "policy": policy,
        "proposal": {
            "proposal_id": "proposal-1", "user_id": "user-1", "intent": intent,
            "offer": offer, "verification": verification, "policy_decision": policy,
            "policy_version": "policy-v1", "created_at": NOW,
        },
        "approval": {
            **BINDING, "approval_request_id": "approval-1",
            "created_at": NOW, "expires_at": NOW + timedelta(minutes=10),
        },
        "payment": {
            **BINDING, "payment_intent_id": "payment-1",
            "idempotency_key": "stable-key-1", "created_at": NOW,
        },
    })


@pytest.mark.parametrize("name", MODELS)
def test_valid_records_round_trip_json(name: str, records: dict) -> None:
    model = MODELS[name].model_validate(records[name])
    assert MODELS[name].model_validate_json(model.model_dump_json()) == model
    assert MODELS[name].model_json_schema()["additionalProperties"] is False


@pytest.mark.parametrize("name", MODELS)
def test_unexpected_fields_are_rejected(name: str, records: dict) -> None:
    records[name]["bypass_policy"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        MODELS[name].model_validate(records[name])


@pytest.mark.parametrize("name,field", MONEY_FIELDS)
@pytest.mark.parametrize("invalid", [-1, 1.5, 1500.0, "150000", True, False, None, Decimal("1")])
def test_money_requires_nonnegative_actual_integers(
    name: str, field: str, invalid: Any, records: dict
) -> None:
    records[name][field] = invalid
    with pytest.raises(ValidationError):
        MODELS[name].model_validate(records[name])


def test_zero_budget_is_explicit_and_large_integer_is_exact(records: dict) -> None:
    records["intent"].update(budget_max_minor=0, approval_threshold_minor=0)
    assert PurchaseIntent(**records["intent"]).budget_max_minor == 0
    # This is above the exact integer range of IEEE-754 double precision.
    records["offer"]["amount_minor"] = 9_007_199_254_740_993
    offer = Offer(**records["offer"])
    assert Offer.model_validate_json(offer.model_dump_json()).amount_minor == 9_007_199_254_740_993


@pytest.mark.parametrize("field", ["budget_max_minor", "approval_threshold_minor"])
def test_missing_budget_does_not_become_unlimited(field: str, records: dict) -> None:
    del records["intent"][field]
    with pytest.raises(ValidationError, match="Field required"):
        PurchaseIntent(**records["intent"])


def test_threshold_cannot_raise_budget(records: dict) -> None:
    records["intent"]["approval_threshold_minor"] = 150_001
    with pytest.raises(ValidationError, match="must not exceed"):
        PurchaseIntent(**records["intent"])


@pytest.mark.parametrize("invalid", [0, -1, True, 1.5, "2"])
def test_quantity_is_a_positive_integer(invalid: Any, records: dict) -> None:
    records["intent"]["quantity"] = invalid
    with pytest.raises(ValidationError):
        PurchaseIntent(**records["intent"])


def test_required_and_preferred_are_preserved_and_cannot_overlap(records: dict) -> None:
    intent = PurchaseIntent(**records["intent"])
    assert intent.required_attributes == {"gym": True}
    assert intent.preferred_attributes == {"private_pool": True}
    records["intent"]["preferred_attributes"]["gym"] = False
    with pytest.raises(ValidationError, match="both required and preferred"):
        PurchaseIntent(**records["intent"])


@pytest.mark.parametrize("name", ["intent", "offer", "policy", "approval", "payment"])
@pytest.mark.parametrize("invalid", ["usd", "US", "USDD", " USD", 840])
def test_currency_code_shape(name: str, invalid: Any, records: dict) -> None:
    records[name]["currency"] = invalid
    with pytest.raises(ValidationError):
        MODELS[name].model_validate(records[name])


@pytest.mark.parametrize("status", list(VerificationStatus))
def test_check_accepts_all_three_verification_states(status: VerificationStatus) -> None:
    result = CheckResult(requirement="gym", status=status, explanation="Structured check")
    assert result.status == status


def test_semantic_pass_requires_evidence_despite_high_confidence(records: dict) -> None:
    records["check"].update(evidence=[], confidence=1.0)
    with pytest.raises(ValidationError, match="semantic PASS requires evidence"):
        CheckResult(**records["check"])


def test_offer_and_unknown_check_accept_missing_evidence(records: dict) -> None:
    records["offer"].pop("evidence")
    assert Offer(**records["offer"]).evidence == {}
    records["check"].update(status="UNKNOWN", evidence=[], confidence=None)
    assert CheckResult(**records["check"]).status == VerificationStatus.UNKNOWN


@pytest.mark.parametrize("field,invalid", [
    ("preference_score", -1), ("preference_score", 101),
    ("preference_score", float("nan")), ("preference_score", float("inf")),
    ("preference_score", True), ("confidence", -0.1), ("confidence", 1.1),
    ("confidence", float("nan")), ("confidence", float("inf")), ("confidence", True),
])
def test_scores_are_finite_and_bounded(field: str, invalid: Any, records: dict) -> None:
    name = "check" if field == "confidence" else "verification"
    records[name][field] = invalid
    with pytest.raises(ValidationError):
        MODELS[name].model_validate(records[name])


@pytest.mark.parametrize("statuses,missing,expected", [
    (["PASS"], [], "PASS"),
    (["PASS", "FAIL", "UNKNOWN"], [], "FAIL"),
    (["PASS", "UNKNOWN"], [], "UNKNOWN"),
    (["PASS"], ["cancellation terms"], "UNKNOWN"),
    ([], ["offer evidence"], "UNKNOWN"),
])
def test_verification_summary_cannot_override_required_checks(
    statuses: list[str], missing: list[str], expected: str, records: dict
) -> None:
    payload = records["verification"]
    payload.update(
        required_checks=[
            {"requirement": f"requirement-{i}", "status": status, "explanation": "Check"}
            for i, status in enumerate(statuses)
        ],
        missing_evidence=missing, status=expected,
    )
    assert VerificationResult(**payload).status == expected
    payload["status"] = "FAIL" if expected == "PASS" else "PASS"
    with pytest.raises(ValidationError, match="contradicts"):
        VerificationResult(**payload)


def test_duplicate_required_checks_are_rejected(records: dict) -> None:
    records["verification"]["required_checks"] *= 2
    with pytest.raises(ValidationError, match="unique requirements"):
        VerificationResult(**records["verification"])


@pytest.mark.parametrize("decision,reason", [
    ("DENY", "BUDGET_EXCEEDED"),
    ("REQUIRE_APPROVAL", "MISSING_EVIDENCE"),
    ("DENY", "CURRENCY_MISMATCH"),
])
def test_denial_and_escalation_require_reason_codes(
    decision: str, reason: str, records: dict
) -> None:
    records["policy"]["decision"] = decision
    with pytest.raises(ValidationError, match="require reason_codes"):
        PolicyDecision(**records["policy"])
    records["policy"]["reason_codes"] = [reason]
    assert PolicyDecision(**records["policy"]).decision == decision
    records["policy"]["reason_codes"] = [reason, reason]
    with pytest.raises(ValidationError, match="unique"):
        PolicyDecision(**records["policy"])


@pytest.mark.parametrize("name,field", [
    ("check", "status"), ("check", "kind"), ("verification", "status"),
    ("policy", "decision"), ("approval", "status"),
    ("payment", "state"), ("payment", "approval_state"),
])
def test_unknown_enums_are_rejected(name: str, field: str, records: dict) -> None:
    records[name][field] = "BYPASSED"
    with pytest.raises(ValidationError):
        MODELS[name].model_validate(records[name])


def test_unknown_policy_reason_is_rejected(records: dict) -> None:
    records["policy"]["reason_codes"] = ["LLM_APPROVED"]
    with pytest.raises(ValidationError):
        PolicyDecision(**records["policy"])


@pytest.mark.parametrize("part,field,invalid", [
    ("verification", "offer_id", "other-offer"),
    ("policy_decision", "amount_minor", 1),
    ("policy_decision", "currency", "EUR"),
    ("policy_decision", "policy_version", "another-version"),
])
def test_proposal_rejects_mismatched_records(
    part: str, field: str, invalid: Any, records: dict
) -> None:
    records["proposal"][part][field] = invalid
    with pytest.raises(ValidationError):
        PurchaseProposal(**records["proposal"])


def test_draft_and_denied_proposals_are_representable(records: dict) -> None:
    proposal = records["proposal"]
    proposal.pop("verification")
    proposal.pop("policy_decision")
    assert PurchaseProposal(**proposal).proposal_digest is None
    proposal["offer"]["amount_minor"] = 162_000
    proposal["offer"]["currency"] = "EUR"
    proposal["policy_decision"] = {
        **records["policy"], "amount_minor": 162_000, "currency": "EUR",
        "decision": "DENY", "reason_codes": ["BUDGET_EXCEEDED", "CURRENCY_MISMATCH"],
    }
    assert PurchaseProposal(**proposal).policy_decision.decision == "DENY"


@pytest.mark.parametrize("name", ["approval", "payment"])
@pytest.mark.parametrize("field", list(BINDING))
def test_every_canonical_binding_field_is_required(name: str, field: str, records: dict) -> None:
    del records[name][field]
    with pytest.raises(ValidationError, match="Field required"):
        MODELS[name].model_validate(records[name])


@pytest.mark.parametrize("name", ["approval", "payment", "proposal"])
@pytest.mark.parametrize("invalid", ["", "not-a-digest", "a" * 63, "G" * 64])
def test_digest_must_be_lowercase_sha256_shape(name: str, invalid: str, records: dict) -> None:
    records[name]["proposal_digest"] = invalid
    with pytest.raises(ValidationError):
        MODELS[name].model_validate(records[name])


@pytest.mark.parametrize("name,field", [
    ("proposal", "created_at"), ("approval", "created_at"),
    ("approval", "expires_at"), ("payment", "created_at"),
])
def test_naive_timestamps_are_rejected(name: str, field: str, records: dict) -> None:
    records[name][field] = NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone_aware"):
        MODELS[name].model_validate(records[name])


@pytest.mark.parametrize("offset", [0, -1])
def test_approval_must_expire_after_creation(offset: int, records: dict) -> None:
    records["approval"]["expires_at"] = NOW + timedelta(seconds=offset)
    with pytest.raises(ValidationError, match="expires_at must be after"):
        ApprovalRequest(**records["approval"])


@pytest.mark.parametrize("status", ["APPROVED", "REJECTED"])
def test_decided_approval_requires_time_inside_window(status: str, records: dict) -> None:
    approval = records["approval"]
    approval["status"] = status
    for invalid in [None, NOW - timedelta(seconds=1), approval["expires_at"]]:
        approval["decided_at"] = invalid
        with pytest.raises(ValidationError):
            ApprovalRequest(**approval)
    approval["decided_at"] = NOW
    assert ApprovalRequest(**approval).status == status


def test_pending_and_expired_approval_history(records: dict) -> None:
    approval = records["approval"]
    approval["decided_at"] = NOW
    with pytest.raises(ValidationError, match="pending"):
        ApprovalRequest(**approval)
    approval["status"] = "EXPIRED"
    assert ApprovalRequest(**approval).decided_at == NOW
    approval["decided_at"] = None
    assert ApprovalRequest(**approval).status == ApprovalStatus.EXPIRED


def test_payment_defaults_are_safe_and_idempotency_is_explicit(records: dict) -> None:
    payment = PaymentIntent(**records["payment"])
    assert payment.state == PaymentState.CREATED
    assert payment.approval_state == ApprovalState.PENDING
    assert PaymentIntent.model_validate_json(payment.model_dump_json()).idempotency_key == (
        payment.idempotency_key
    )
    for invalid in ["", " ", None, 123]:
        records["payment"]["idempotency_key"] = invalid
        with pytest.raises(ValidationError):
            PaymentIntent(**records["payment"])
    del records["payment"]["idempotency_key"]
    with pytest.raises(ValidationError):
        PaymentIntent(**records["payment"])


@pytest.mark.parametrize("state", ["APPROVED", "REJECTED", "EXPIRED"])
def test_payment_approval_needs_reference(state: str, records: dict) -> None:
    payment = records["payment"]
    payment["approval_state"] = state
    with pytest.raises(ValidationError, match="requires approval_request_id"):
        PaymentIntent(**payment)
    payment["approval_request_id"] = "approval-1"
    assert PaymentIntent(**payment).approval_state == state
    payment["approval_state"] = "NOT_REQUIRED"
    with pytest.raises(ValidationError, match="NOT_REQUIRED"):
        PaymentIntent(**payment)
    payment.pop("approval_request_id")
    assert PaymentIntent(**payment).approval_state == ApprovalState.NOT_REQUIRED


def test_mutable_defaults_are_not_shared(records: dict) -> None:
    payload = records["intent"]
    payload.pop("required_attributes")
    first, second = PurchaseIntent(**payload), PurchaseIntent(**payload)
    first.required_attributes["gym"] = True
    assert second.required_attributes == {}



def test_nested_proposal_inputs_use_the_same_boundary_rules(records: dict) -> None:
    records["proposal"]["offer"]["amount_minor"] = "118000"
    with pytest.raises(ValidationError, match="int_type"):
        PurchaseProposal(**records["proposal"])
    records["proposal"]["offer"]["amount_minor"] = 118_000
    records["proposal"]["intent"]["override_budget"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        PurchaseProposal(**records["proposal"])


def test_semantic_pass_cannot_use_blank_evidence(records: dict) -> None:
    records["check"]["evidence"] = ["   "]
    with pytest.raises(ValidationError):
        CheckResult(**records["check"])
