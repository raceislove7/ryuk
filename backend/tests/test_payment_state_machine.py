"""Contract matrix plus lifecycle/uncertainty and immutable-binding regression tests."""

from datetime import datetime, timezone
from itertools import product
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import PaymentIntent, PaymentState
from app.services.payment_state_machine import (
    IllegalPaymentTransition,
    PaymentEvent,
    StalePaymentState,
    allowed_transitions,
    can_transition,
    transition_payment_intent,
    transition_state,
)

# Independent behavioral contract: events absent here must be rejected, even when
# the target would otherwise be structurally reachable by a different event.
EXPECTED = {
    ("CREATED", "START_POLICY_CHECK"): "POLICY_CHECK",
    ("CREATED", "CANCEL"): "FAILED",
    ("POLICY_CHECK", "POLICY_REQUIRES_APPROVAL"): "AWAITING_APPROVAL",
    ("POLICY_CHECK", "POLICY_ALLOWED"): "CHECKOUT_READY",
    ("POLICY_CHECK", "POLICY_DENIED"): "FAILED",
    ("POLICY_CHECK", "CANCEL"): "FAILED",
    ("AWAITING_APPROVAL", "APPROVAL_RECORDED"): "POLICY_CHECK",
    ("AWAITING_APPROVAL", "RECHECK_POLICY"): "POLICY_CHECK",
    ("AWAITING_APPROVAL", "APPROVAL_REJECTED"): "FAILED",
    ("AWAITING_APPROVAL", "CANCEL"): "FAILED",
    ("CHECKOUT_READY", "START_BUYER_APPROVAL"): "AWAITING_PAYPAL_BUYER",
    ("CHECKOUT_READY", "RECHECK_POLICY"): "POLICY_CHECK",
    ("CHECKOUT_READY", "CANCEL"): "FAILED",
    ("AWAITING_PAYPAL_BUYER", "REQUEST_CAPTURE"): "CAPTURE_PENDING",
    ("AWAITING_PAYPAL_BUYER", "RECHECK_POLICY"): "POLICY_CHECK",
    ("AWAITING_PAYPAL_BUYER", "BUYER_DECLINED"): "FAILED",
    ("AWAITING_PAYPAL_BUYER", "CANCEL"): "FAILED",
    ("CAPTURE_PENDING", "CAPTURE_CONFIRMED"): "SUCCEEDED",
    ("CAPTURE_PENDING", "CAPTURE_FAILED"): "FAILED",
    ("CAPTURE_PENDING", "CAPTURE_UNCERTAIN"): "PENDING_PROVIDER",
    ("PENDING_PROVIDER", "RECONCILED_SUCCESS"): "SUCCEEDED",
    ("PENDING_PROVIDER", "RECONCILED_FAILURE"): "FAILED",
}


@pytest.fixture
def payment() -> PaymentIntent:
    return PaymentIntent(
        payment_intent_id="payment-1",
        idempotency_key="stable-key-1",
        proposal_id="proposal-1",
        user_id="user-1",
        offer_id="synthetic-hotel-001",
        merchant_id="synthetic-hotel-merchant-001",
        amount_minor=118_000,
        currency="USD",
        policy_version="policy-v1",
        verification_snapshot_id="snapshot-1",
        proposal_digest="a" * 64,
        approval_state="NOT_REQUIRED",
        created_at=datetime(2026, 11, 11, 12, tzinfo=timezone.utc),
    )


def test_state_vocabulary_is_exactly_the_nine_requested_states() -> None:
    assert {state.value for state in PaymentState} == {
        "CREATED",
        "POLICY_CHECK",
        "AWAITING_APPROVAL",
        "CHECKOUT_READY",
        "AWAITING_PAYPAL_BUYER",
        "CAPTURE_PENDING",
        "SUCCEEDED",
        "FAILED",
        "PENDING_PROVIDER",
    }


@pytest.mark.parametrize("state,event", list(product(PaymentState, PaymentEvent)))
def test_all_state_event_combinations_enforce_contract_and_preserve_terms(
    payment: PaymentIntent, state: PaymentState, event: PaymentEvent
) -> None:
    payment = PaymentIntent.model_validate(payment.model_dump() | {"state": state})
    before = payment.model_dump()
    expected = EXPECTED.get((state.value, event.value))
    if expected is None:
        with pytest.raises(IllegalPaymentTransition):
            transition_payment_intent(payment, event, expected_state=state)
    else:
        changed = transition_payment_intent(payment, event, expected_state=state)
        assert changed.state == expected
        assert changed is not payment
        assert changed.model_dump(exclude={"state"}) == payment.model_dump(exclude={"state"})
        assert PaymentIntent.model_validate_json(changed.model_dump_json()) == changed
    assert payment.model_dump() == before


@pytest.mark.parametrize("current,target", list(product(PaymentState, PaymentState)))
def test_state_reachability_matches_the_published_graph(
    current: PaymentState, target: PaymentState
) -> None:
    expected = {to for (source, _), to in EXPECTED.items() if source == current.value}
    assert can_transition(current, target) is (target.value in expected)
    assert {state.value for state in allowed_transitions(current)} == expected


@pytest.mark.parametrize("needs_application_approval", [False, True])
def test_success_path_including_fresh_policy_after_application_approval(
    payment: PaymentIntent, needs_application_approval: bool
) -> None:
    events = [PaymentEvent.START_POLICY_CHECK]
    if needs_application_approval:
        events += [PaymentEvent.POLICY_REQUIRES_APPROVAL, PaymentEvent.APPROVAL_RECORDED]
    events += [
        PaymentEvent.POLICY_ALLOWED,
        PaymentEvent.START_BUYER_APPROVAL,
        PaymentEvent.REQUEST_CAPTURE,
        PaymentEvent.CAPTURE_CONFIRMED,
    ]
    for event in events:
        payment = transition_payment_intent(payment, event)
    assert payment.state == PaymentState.SUCCEEDED
    assert payment.idempotency_key == "stable-key-1" and payment.amount_minor == 118_000


@pytest.mark.parametrize(
    "event,terminal",
    [
        (PaymentEvent.RECONCILED_SUCCESS, PaymentState.SUCCEEDED),
        (PaymentEvent.RECONCILED_FAILURE, PaymentState.FAILED),
    ],
)
def test_capture_timeout_needs_explicit_reconciliation(
    payment: PaymentIntent, event: PaymentEvent, terminal: PaymentState
) -> None:
    payment = PaymentIntent.model_validate(payment.model_dump() | {"state": "CAPTURE_PENDING"})
    uncertain = transition_payment_intent(payment, PaymentEvent.CAPTURE_UNCERTAIN)
    assert uncertain.state == PaymentState.PENDING_PROVIDER
    for forbidden in (
        PaymentEvent.REQUEST_CAPTURE,
        PaymentEvent.CANCEL,
        PaymentEvent.CAPTURE_FAILED,
        PaymentEvent.CAPTURE_CONFIRMED,
    ):
        with pytest.raises(IllegalPaymentTransition):
            transition_payment_intent(uncertain, forbidden)
    final = transition_payment_intent(uncertain, event)
    assert final.state == terminal and final.idempotency_key == payment.idempotency_key


def test_application_approval_does_not_skip_policy_recheck() -> None:
    assert transition_state("AWAITING_APPROVAL", "APPROVAL_RECORDED") == PaymentState.POLICY_CHECK
    assert not can_transition("AWAITING_APPROVAL", "CHECKOUT_READY")
    with pytest.raises(IllegalPaymentTransition):
        transition_state("AWAITING_APPROVAL", "POLICY_ALLOWED")


@pytest.mark.parametrize("state", ["CHECKOUT_READY", "AWAITING_PAYPAL_BUYER"])
def test_pre_capture_invalidation_can_return_to_policy(state: str) -> None:
    assert transition_state(state, "RECHECK_POLICY") == PaymentState.POLICY_CHECK


def test_expected_state_rejects_stale_local_inputs(payment: PaymentIntent) -> None:
    with pytest.raises(StalePaymentState):
        transition_payment_intent(
            payment, PaymentEvent.START_POLICY_CHECK, expected_state=PaymentState.POLICY_CHECK
        )
    assert payment.state == PaymentState.CREATED


@pytest.mark.parametrize("invalid", ["VERIFYING", "APPROVED", "created", "", None, True, {}])
def test_unknown_or_removed_states_are_rejected(invalid: Any) -> None:
    with pytest.raises(ValidationError):
        allowed_transitions(invalid)
    with pytest.raises(ValidationError):
        can_transition(PaymentState.CREATED, invalid)


@pytest.mark.parametrize("invalid", ["SUCCEEDED", "ALLOW", "capture_confirmed", "", None, True, {}])
def test_arbitrary_targets_or_model_commands_are_not_events(
    payment: PaymentIntent, invalid: Any
) -> None:
    with pytest.raises(ValidationError):
        transition_payment_intent(payment, invalid)


def test_mutated_invalid_models_cannot_enter_the_transition_graph(payment: PaymentIntent) -> None:
    payment.amount_minor = True
    with pytest.raises(ValidationError):
        transition_payment_intent(payment, PaymentEvent.START_POLICY_CHECK)


def test_duplicate_terminal_confirmation_is_not_a_second_transition(payment: PaymentIntent) -> None:
    payment = PaymentIntent.model_validate(payment.model_dump() | {"state": "CAPTURE_PENDING"})
    complete = transition_payment_intent(payment, PaymentEvent.CAPTURE_CONFIRMED)
    with pytest.raises(IllegalPaymentTransition):
        transition_payment_intent(complete, PaymentEvent.CAPTURE_CONFIRMED)
    assert complete.state == PaymentState.SUCCEEDED
