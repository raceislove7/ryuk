"""Canonical hashing, owned approval lifecycle, exact expiry, invalidation and replay."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import ApprovalStatus, PaymentIntent, PurchaseIntent, PurchaseProposal
from app.schemas.policy import AttemptSnapshot, BudgetSnapshot, FinancialPolicy
from app.services.approvals import (
    ApprovalAccessError,
    ApprovalPolicyError,
    ApprovalStateError,
    InMemoryApprovalService,
    ProposalConflictError,
)
from app.services.catalog import CatalogService
from app.services.policy import evaluate_policy
from app.services.proposal_binding import (
    InvalidProposalBinding,
    bind_proposal,
    canonical_proposal_digest,
    require_proposal_binding,
)
from app.services.verifier import verify_offer

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


@pytest.fixture
def setup() -> dict[str, Any]:
    offer = CatalogService().get_offer("synthetic-hotel-002")
    intent = PurchaseIntent(
        category="hotel",
        query="Hotel with a gym and optional private pool",
        currency="USD",
        budget_max_minor=150_000,
        approval_threshold_minor=130_000,
        required_attributes={"gym": True},
        preferred_attributes={"private_pool": True},
    )
    raw = PurchaseProposal(
        proposal_id="proposal-1",
        user_id="user-1",
        intent=intent,
        offer=offer,
        policy_version="policy-v1",
        created_at=NOW - timedelta(minutes=1),
        verification=verify_offer(intent, offer),
    )
    service = InMemoryApprovalService()
    bound = service.register_proposal(raw, at=NOW)
    return {
        "service": service,
        "proposal": bound,
        "policy": FinancialPolicy(
            user_id="user-1",
            version="policy-v1",
            currency="USD",
            max_amount_minor=150_000,
            approval_threshold_minor=130_000,
            allowed_merchant_ids=frozenset({offer.merchant_id}),
        ),
        "budget": BudgetSnapshot(
            user_id="user-1", currency="USD", limit_minor=300_000, settled_minor=0, reserved_minor=0
        ),
        "attempts": AttemptSnapshot(user_id="user-1", proposal_id="proposal-1", state="CLEAR"),
    }


def inputs(setup: dict) -> dict:
    return {
        "actor_user_id": "user-1",
        **{key: setup[key] for key in ("policy", "budget", "attempts")},
    }


def grant(setup: dict) -> Any:
    service = setup["service"]
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))
    return service.approve_request(
        request.approval_request_id, at=NOW + timedelta(seconds=1), **inputs(setup)
    )


def changed_proposal(proposal: PurchaseProposal, field: str) -> PurchaseProposal:
    changed = proposal.model_copy(deep=True)
    if field == "user":
        changed.user_id = "user-2"
    elif field == "offer":
        changed.offer.offer_id = "changed-offer"
    elif field == "merchant":
        changed.offer.merchant_id = "changed-merchant"
    elif field == "amount":
        changed.offer.amount_minor = 140_000
    elif field == "currency":
        changed.offer.currency = "EUR"
    elif field == "policy":
        changed.policy_version = "policy-v2"
    elif field == "snapshot":
        changed.offer.evidence["gym"] = ["Updated synthetic evidence"]
    elif field == "proposal_id":
        changed.proposal_id = "proposal-2"
    elif field == "created_at":
        changed.created_at -= timedelta(seconds=1)
    changed.verification = verify_offer(changed.intent, changed.offer)
    return changed


def test_digest_is_stable_versioned_content_hash_and_leaves_inputs_unchanged(setup: dict) -> None:
    proposal = setup["proposal"]
    before = proposal.model_dump()
    first = canonical_proposal_digest(proposal)
    assert first == canonical_proposal_digest(proposal) == proposal.proposal_digest
    assert len(first) == 64 and int(first, 16) >= 0
    assert proposal.model_dump() == before
    require_proposal_binding(proposal)
    assert bind_proposal(proposal) == proposal


def test_map_order_and_equivalent_timezone_do_not_change_digest(setup: dict) -> None:
    proposal = setup["proposal"].model_copy(deep=True)
    proposal.created_at = proposal.created_at.astimezone(timezone(timedelta(hours=5, minutes=30)))
    proposal.offer.attributes = dict(reversed(list(proposal.offer.attributes.items())))
    proposal.offer.evidence = dict(reversed(list(proposal.offer.evidence.items())))
    assert canonical_proposal_digest(proposal) == setup["proposal"].proposal_digest


@pytest.mark.parametrize(
    "field",
    [
        "user",
        "offer",
        "merchant",
        "amount",
        "currency",
        "policy",
        "snapshot",
        "proposal_id",
        "created_at",
    ],
)
def test_every_bound_identity_or_term_changes_digest(setup: dict, field: str) -> None:
    original = setup["proposal"]
    changed = changed_proposal(original, field)
    assert canonical_proposal_digest(changed) != original.proposal_digest
    with pytest.raises(InvalidProposalBinding):
        require_proposal_binding(changed)


@pytest.mark.parametrize("kind", ["absent", "stale", "fabricated_id", "fake_hash"])
def test_missing_or_forged_verification_or_digest_is_not_binding(setup: dict, kind: str) -> None:
    proposal = setup["proposal"].model_copy(deep=True)
    if kind == "absent":
        proposal.verification = None
    elif kind == "stale":
        proposal.offer.amount_minor += 1
    elif kind == "fabricated_id":
        proposal.verification.verification_snapshot_id = "invented-snapshot"
    else:
        proposal.proposal_digest = "a" * 64
    with pytest.raises(InvalidProposalBinding):
        require_proposal_binding(proposal)


def test_noninteger_money_is_not_normalized_into_a_digest(setup: dict) -> None:
    proposal = setup["proposal"].model_copy(deep=True)
    proposal.offer.amount_minor = True
    with pytest.raises(ValidationError):
        canonical_proposal_digest(proposal)


def test_policy_decision_metadata_is_not_an_approval_term(setup: dict) -> None:
    proposal = setup["proposal"].model_copy(deep=True)
    proposal.policy_decision = evaluate_policy(
        proposal, setup["policy"], setup["budget"], setup["attempts"], evaluated_at=NOW
    )
    assert canonical_proposal_digest(proposal) == setup["proposal"].proposal_digest


def test_request_copies_all_canonical_terms_and_starts_pending(setup: dict) -> None:
    request = setup["service"].create_request("proposal-1", at=NOW, **inputs(setup))
    proposal = setup["proposal"]
    assert request.status == ApprovalStatus.PENDING and request.decided_at is None
    assert request.expires_at == NOW + timedelta(minutes=10)
    assert request.user_id == proposal.user_id
    assert request.offer_id == proposal.offer.offer_id
    assert request.merchant_id == proposal.offer.merchant_id
    assert request.amount_minor == proposal.offer.amount_minor
    assert request.currency == proposal.offer.currency
    assert request.policy_version == proposal.policy_version
    assert request.verification_snapshot_id == proposal.verification.verification_snapshot_id
    assert request.proposal_digest == proposal.proposal_digest


def test_pending_request_retries_do_not_extend_expiry(setup: dict) -> None:
    service = setup["service"]
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))
    retry = service.create_request("proposal-1", at=NOW + timedelta(minutes=9), **inputs(setup))
    assert retry == request


def test_approval_and_checkout_rerun_binding_and_policy(setup: dict) -> None:
    approved = grant(setup)
    assert approved.status == ApprovalStatus.APPROVED
    result = setup["service"].revalidate_for_checkout(
        "proposal-1",
        at=NOW + timedelta(seconds=2),
        approval_request_id=approved.approval_request_id,
        **inputs(setup),
    )
    assert result.decision == "ALLOW_ELIGIBLE_FOR_CHECKOUT"
    assert result.reason_codes == ["APPROVAL_GRANTED"]


@pytest.mark.parametrize(
    "field", ["user", "offer", "merchant", "amount", "currency", "policy", "snapshot", "created_at"]
)
def test_canonical_bound_field_changes_permanently_invalidate(setup: dict, field: str) -> None:
    approved = grant(setup)
    service, original = setup["service"], setup["proposal"]
    changed = changed_proposal(original, field)
    service.register_proposal(
        changed, at=NOW + timedelta(seconds=2), expected_digest=original.proposal_digest
    )
    history = service.get_request(
        approved.approval_request_id, actor_user_id="user-1", at=NOW + timedelta(seconds=2)
    )
    assert history.status == ApprovalStatus.INVALIDATED
    assert history.decided_at == approved.decided_at
    with pytest.raises((ApprovalStateError, ApprovalAccessError)):
        service.approve_request(
            approved.approval_request_id, at=NOW + timedelta(seconds=3), **inputs(setup)
        )


def test_restoring_old_terms_does_not_resurrect_old_consent(setup: dict) -> None:
    approved = grant(setup)
    service, original = setup["service"], setup["proposal"]
    changed = service.register_proposal(
        changed_proposal(original, "amount"),
        at=NOW + timedelta(seconds=2),
        expected_digest=original.proposal_digest,
    )
    service.register_proposal(
        original, at=NOW + timedelta(seconds=3), expected_digest=changed.proposal_digest
    )
    result = service.revalidate_for_checkout(
        "proposal-1", at=NOW + timedelta(seconds=4), **inputs(setup)
    )
    assert result.decision == "DENY" and "PROPOSAL_CHANGED" in result.reason_codes
    assert (
        service.get_request(
            approved.approval_request_id, actor_user_id="user-1", at=NOW + timedelta(seconds=4)
        ).status
        == ApprovalStatus.INVALIDATED
    )


def test_approval_cannot_be_replayed_on_another_proposal(setup: dict) -> None:
    approved = grant(setup)
    service = setup["service"]
    other = changed_proposal(setup["proposal"], "proposal_id")
    service.register_proposal(other, at=NOW + timedelta(seconds=2))
    with pytest.raises(ApprovalStateError):
        service.revalidate_for_checkout(
            "proposal-2",
            at=NOW + timedelta(seconds=2),
            approval_request_id=approved.approval_request_id,
            **inputs(setup),
        )


@pytest.mark.parametrize(
    "operation", ["create", "approve", "reject", "read", "checkout", "proposal"]
)
def test_another_user_cannot_read_or_decide(setup: dict, operation: str) -> None:
    service = setup["service"]
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))
    other = inputs(setup) | {"actor_user_id": "user-2"}
    with pytest.raises(ApprovalAccessError):
        if operation == "create":
            service.create_request("proposal-1", at=NOW, **other)
        elif operation == "approve":
            service.approve_request(request.approval_request_id, at=NOW, **other)
        elif operation == "reject":
            service.reject_request(request.approval_request_id, at=NOW, actor_user_id="user-2")
        elif operation == "read":
            service.get_request(request.approval_request_id, at=NOW, actor_user_id="user-2")
        elif operation == "proposal":
            service.get_proposal("proposal-1", actor_user_id="user-2")
        else:
            service.revalidate_for_checkout("proposal-1", at=NOW, **other)


@pytest.mark.parametrize("seconds", [600, 601])
def test_exact_expiry_or_later_cannot_reuse_approved_grant(setup: dict, seconds: int) -> None:
    approved = grant(setup)
    at = NOW + timedelta(seconds=seconds)
    service = setup["service"]
    result = service.revalidate_for_checkout("proposal-1", at=at, **inputs(setup))
    assert result.decision == "REQUIRE_APPROVAL" and "APPROVAL_EXPIRED" in result.reason_codes
    assert service.get_request(
        approved.approval_request_id, actor_user_id="user-1", at=at
    ).status == (ApprovalStatus.EXPIRED)


def test_pending_expiry_requires_fresh_request_and_consent(setup: dict) -> None:
    service = setup["service"]
    old = service.create_request("proposal-1", at=NOW, **inputs(setup))
    with pytest.raises(ApprovalStateError):
        service.approve_request(old.approval_request_id, at=old.expires_at, **inputs(setup))
    fresh = service.create_request("proposal-1", at=old.expires_at, **inputs(setup))
    assert fresh.approval_request_id != old.approval_request_id
    assert fresh.status == ApprovalStatus.PENDING
    assert fresh.expires_at > old.expires_at
    with pytest.raises(ApprovalStateError):
        service.revalidate_for_checkout(
            "proposal-1",
            at=old.expires_at,
            approval_request_id=old.approval_request_id,
            **inputs(setup),
        )


def test_decisions_are_one_time_and_reject_is_not_spending_authority(setup: dict) -> None:
    service = setup["service"]
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))
    setup["budget"].limit_minor = 0
    rejected = service.reject_request(request.approval_request_id, actor_user_id="user-1", at=NOW)
    assert rejected.status == ApprovalStatus.REJECTED
    with pytest.raises(ApprovalStateError):
        service.approve_request(request.approval_request_id, at=NOW, **inputs(setup))
    assert service.revalidate_for_checkout("proposal-1", at=NOW, **inputs(setup)).decision == "DENY"


def test_a_new_review_revokes_prior_grant_even_if_new_review_is_rejected(setup: dict) -> None:
    old = grant(setup)
    service = setup["service"]
    new = service.create_request("proposal-1", at=NOW + timedelta(seconds=2), **inputs(setup))
    service.reject_request(
        new.approval_request_id, actor_user_id="user-1", at=NOW + timedelta(seconds=3)
    )
    result = service.revalidate_for_checkout(
        "proposal-1", at=NOW + timedelta(seconds=4), **inputs(setup)
    )
    assert result.decision == "DENY" and "APPROVAL_REJECTED" in result.reason_codes
    with pytest.raises(ApprovalStateError):
        service.revalidate_for_checkout(
            "proposal-1",
            at=NOW + timedelta(seconds=4),
            approval_request_id=old.approval_request_id,
            **inputs(setup),
        )


@pytest.mark.parametrize("condition", ["budget", "duplicate", "uncertain_history"])
def test_current_hard_policy_denial_blocks_creation_and_approval(
    setup: dict, condition: str
) -> None:
    service = setup["service"]
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))
    if condition == "budget":
        setup["budget"].limit_minor = 1
    else:
        setup["attempts"].state = "DUPLICATE" if condition == "duplicate" else "UNKNOWN"
    with pytest.raises(ApprovalPolicyError):
        service.approve_request(request.approval_request_id, at=NOW, **inputs(setup))
    with pytest.raises(ApprovalPolicyError):
        service.create_request("proposal-1", at=NOW, **inputs(setup))
    assert service.get_request(
        request.approval_request_id, actor_user_id="user-1", at=NOW
    ).status == (ApprovalStatus.PENDING)


def test_checkout_rechecks_current_funds_after_consent(setup: dict) -> None:
    grant(setup)
    setup["budget"].reserved_minor = 299_999
    result = setup["service"].revalidate_for_checkout(
        "proposal-1", at=NOW + timedelta(seconds=2), **inputs(setup)
    )
    assert result.decision == "DENY" and "BUDGET_EXCEEDED" in result.reason_codes


def test_policy_version_change_revokes_consent_even_if_version_is_later_restored(
    setup: dict,
) -> None:
    old = grant(setup)
    service = setup["service"]
    setup["policy"].version = "policy-v2"
    assert (
        service.revalidate_for_checkout(
            "proposal-1", at=NOW + timedelta(seconds=2), **inputs(setup)
        ).decision
        == "DENY"
    )
    setup["policy"].version = "policy-v1"
    assert (
        service.revalidate_for_checkout(
            "proposal-1", at=NOW + timedelta(seconds=3), **inputs(setup)
        ).decision
        == "DENY"
    )
    assert (
        service.get_request(
            old.approval_request_id, actor_user_id="user-1", at=NOW + timedelta(seconds=3)
        ).status
        == ApprovalStatus.INVALIDATED
    )


def test_returned_object_mutations_cannot_create_or_extend_consent(setup: dict) -> None:
    service = setup["service"]
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))
    request.status = ApprovalStatus.APPROVED
    request.expires_at += timedelta(days=1)
    request.amount_minor = 1
    proposal = service.get_proposal("proposal-1", actor_user_id="user-1")
    proposal.offer.amount_minor = 1
    result = service.revalidate_for_checkout("proposal-1", at=NOW, **inputs(setup))
    assert result.decision == "REQUIRE_APPROVAL" and "APPROVAL_PENDING" in result.reason_codes
    with pytest.raises(ApprovalStateError):
        service.approve_request(
            request.approval_request_id, at=NOW + timedelta(minutes=10), **inputs(setup)
        )


def test_hash_shaped_forgery_cannot_satisfy_pure_policy(setup: dict) -> None:
    old = grant(setup)
    proposal = setup["proposal"].model_copy(deep=True)
    proposal.proposal_digest = "a" * 64
    old.proposal_digest = "a" * 64
    result = evaluate_policy(
        proposal,
        setup["policy"],
        setup["budget"],
        setup["attempts"],
        evaluated_at=NOW + timedelta(seconds=2),
        approval=old,
    )
    assert result.decision == "DENY" and "PROPOSAL_CHANGED" in result.reason_codes


def test_stale_update_is_rejected_without_overwriting_canonical_terms(setup: dict) -> None:
    service = setup["service"]
    changed = changed_proposal(setup["proposal"], "amount")
    with pytest.raises(ProposalConflictError):
        service.register_proposal(changed, at=NOW)
    assert service.get_proposal("proposal-1", actor_user_id="user-1") == setup["proposal"]


def test_identical_registration_does_not_revoke_a_grant(setup: dict) -> None:
    old = grant(setup)
    service = setup["service"]
    service.register_proposal(setup["proposal"], at=NOW + timedelta(seconds=2))
    assert (
        service.get_request(
            old.approval_request_id, actor_user_id="user-1", at=NOW + timedelta(seconds=2)
        ).status
        == ApprovalStatus.APPROVED
    )


def test_double_approval_cannot_reset_consent_or_decision_timestamp(setup: dict) -> None:
    service = setup["service"]
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))

    def decide() -> str:
        try:
            service.approve_request(
                request.approval_request_id, at=NOW + timedelta(seconds=1), **inputs(setup)
            )
            return "approved"
        except ApprovalStateError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: decide(), range(2)))
    assert sorted(outcomes) == ["approved", "blocked"]


def test_parallel_updates_use_digest_compare_and_swap(setup: dict) -> None:
    service = setup["service"]
    original = setup["proposal"]

    def update(amount: int) -> str:
        proposal = original.model_copy(deep=True)
        proposal.offer.amount_minor = amount
        proposal.verification = verify_offer(proposal.intent, proposal.offer)
        try:
            service.register_proposal(proposal, at=NOW, expected_digest=original.proposal_digest)
            return "updated"
        except ProposalConflictError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, [140_000, 141_000]))
    assert sorted(outcomes) == ["blocked", "updated"]
    require_proposal_binding(service.get_proposal("proposal-1", actor_user_id="user-1"))


@pytest.mark.parametrize("ttl", [timedelta(0), timedelta(seconds=-1), timedelta(hours=2), None, 10])
def test_ttl_is_backend_bounded_positive_duration(ttl: Any) -> None:
    with pytest.raises(ValueError):
        InMemoryApprovalService(ttl=ttl)


def test_time_cannot_be_naive_or_moved_backwards(setup: dict) -> None:
    service = setup["service"]
    with pytest.raises(ValidationError):
        service.create_request("proposal-1", at=NOW.replace(tzinfo=None), **inputs(setup))
    request = service.create_request("proposal-1", at=NOW, **inputs(setup))
    service.get_request(
        request.approval_request_id, actor_user_id="user-1", at=NOW + timedelta(minutes=11)
    )
    with pytest.raises(ValueError):
        service.approve_request(request.approval_request_id, at=NOW, **inputs(setup))


def test_process_restart_cannot_restore_a_client_held_grant(setup: dict) -> None:
    old = grant(setup)
    restarted = InMemoryApprovalService()
    restarted.register_proposal(setup["proposal"], at=NOW + timedelta(seconds=2))
    with pytest.raises(ApprovalAccessError):
        restarted.approve_request(
            old.approval_request_id, at=NOW + timedelta(seconds=2), **inputs(setup)
        )
    assert (
        restarted.revalidate_for_checkout(
            "proposal-1", at=NOW + timedelta(seconds=2), **inputs(setup)
        ).decision
        == "REQUIRE_APPROVAL"
    )


def test_invalidated_payment_approval_still_requires_its_request_reference(setup: dict) -> None:
    proposal = setup["proposal"]
    data = {
        "payment_intent_id": "payment-1",
        "idempotency_key": "stable-test-key",
        "created_at": NOW,
        "proposal_id": proposal.proposal_id,
        "user_id": proposal.user_id,
        "offer_id": proposal.offer.offer_id,
        "merchant_id": proposal.offer.merchant_id,
        "amount_minor": proposal.offer.amount_minor,
        "currency": proposal.offer.currency,
        "policy_version": proposal.policy_version,
        "verification_snapshot_id": proposal.verification.verification_snapshot_id,
        "proposal_digest": proposal.proposal_digest,
        "approval_state": "INVALIDATED",
    }
    with pytest.raises(ValidationError, match="requires approval_request_id"):
        PaymentIntent(**data)
    data["approval_request_id"] = "invalidated-request-1"
    assert PaymentIntent(**data).approval_state == "INVALIDATED"
