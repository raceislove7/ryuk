"""Provider-neutral, side-effect-free payment transitions for trusted backend events.

This graph does not authenticate provider events, approve spending, reserve funds,
perform capture, or persist state. A backend coordinator must establish those
preconditions and atomically persist the resulting state and audit event.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from pydantic import TypeAdapter

from app.schemas import PaymentIntent, PaymentState


class PaymentEvent(StrEnum):
    START_POLICY_CHECK = "START_POLICY_CHECK"
    POLICY_REQUIRES_APPROVAL = "POLICY_REQUIRES_APPROVAL"
    POLICY_ALLOWED = "POLICY_ALLOWED"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_RECORDED = "APPROVAL_RECORDED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    RECHECK_POLICY = "RECHECK_POLICY"
    START_BUYER_APPROVAL = "START_BUYER_APPROVAL"
    BUYER_DECLINED = "BUYER_DECLINED"
    REQUEST_CAPTURE = "REQUEST_CAPTURE"
    CAPTURE_CONFIRMED = "CAPTURE_CONFIRMED"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    CAPTURE_UNCERTAIN = "CAPTURE_UNCERTAIN"
    RECONCILED_SUCCESS = "RECONCILED_SUCCESS"
    RECONCILED_FAILURE = "RECONCILED_FAILURE"
    CANCEL = "CANCEL"


class IllegalPaymentTransition(ValueError):
    """The event is not legal from the current state; no updated intent is returned."""


class StalePaymentState(ValueError):
    """The caller's expected state does not match the supplied current record."""


# Both levels are immutable; consumers cannot add a transition or alter a target.
_TRANSITIONS: Mapping[PaymentState, Mapping[PaymentEvent, PaymentState]] = MappingProxyType(
    {
        state: MappingProxyType(events)
        for state, events in {
            PaymentState.CREATED: {
                PaymentEvent.START_POLICY_CHECK: PaymentState.POLICY_CHECK,
                PaymentEvent.CANCEL: PaymentState.FAILED,
            },
            PaymentState.POLICY_CHECK: {
                PaymentEvent.POLICY_REQUIRES_APPROVAL: PaymentState.AWAITING_APPROVAL,
                PaymentEvent.POLICY_ALLOWED: PaymentState.CHECKOUT_READY,
                PaymentEvent.POLICY_DENIED: PaymentState.FAILED,
                PaymentEvent.CANCEL: PaymentState.FAILED,
            },
            PaymentState.AWAITING_APPROVAL: {
                PaymentEvent.APPROVAL_RECORDED: PaymentState.POLICY_CHECK,
                PaymentEvent.RECHECK_POLICY: PaymentState.POLICY_CHECK,
                PaymentEvent.APPROVAL_REJECTED: PaymentState.FAILED,
                PaymentEvent.CANCEL: PaymentState.FAILED,
            },
            PaymentState.CHECKOUT_READY: {
                PaymentEvent.START_BUYER_APPROVAL: PaymentState.AWAITING_PAYPAL_BUYER,
                PaymentEvent.RECHECK_POLICY: PaymentState.POLICY_CHECK,
                PaymentEvent.CANCEL: PaymentState.FAILED,
            },
            PaymentState.AWAITING_PAYPAL_BUYER: {
                PaymentEvent.REQUEST_CAPTURE: PaymentState.CAPTURE_PENDING,
                PaymentEvent.RECHECK_POLICY: PaymentState.POLICY_CHECK,
                PaymentEvent.BUYER_DECLINED: PaymentState.FAILED,
                PaymentEvent.CANCEL: PaymentState.FAILED,
            },
            PaymentState.CAPTURE_PENDING: {
                PaymentEvent.CAPTURE_CONFIRMED: PaymentState.SUCCEEDED,
                PaymentEvent.CAPTURE_FAILED: PaymentState.FAILED,
                PaymentEvent.CAPTURE_UNCERTAIN: PaymentState.PENDING_PROVIDER,
            },
            PaymentState.PENDING_PROVIDER: {
                PaymentEvent.RECONCILED_SUCCESS: PaymentState.SUCCEEDED,
                PaymentEvent.RECONCILED_FAILURE: PaymentState.FAILED,
            },
            PaymentState.SUCCEEDED: {},
            PaymentState.FAILED: {},
        }.items()
    }
)


def allowed_transitions(state: PaymentState) -> frozenset[PaymentState]:
    """Read-only target set for introspection, not financial authorization."""
    current = TypeAdapter(PaymentState).validate_python(state)
    return frozenset(_TRANSITIONS[current].values())


def can_transition(current_state: PaymentState, target_state: PaymentState) -> bool:
    """Return structural reachability in one step; reject unknown state values."""
    target = TypeAdapter(PaymentState).validate_python(target_state)
    return target in allowed_transitions(current_state)


def transition_state(current_state: PaymentState, event: PaymentEvent) -> PaymentState:
    """Resolve a trusted backend event through the only allowed transition table."""
    current = TypeAdapter(PaymentState).validate_python(current_state)
    action = TypeAdapter(PaymentEvent).validate_python(event)
    target = _TRANSITIONS[current].get(action)
    if target is None:
        raise IllegalPaymentTransition(f"Event {action.value} is not allowed from {current.value}.")
    return target


def transition_payment_intent(
    payment: PaymentIntent, event: PaymentEvent, *, expected_state: PaymentState | None = None
) -> PaymentIntent:
    """Return a validated state-only update, preserving identity, terms, and idempotency.

    expected_state is a local stale-input check, not a durable compare-and-swap.
    Confirming success requires a verified provider event from the later adapter;
    valid event spelling alone does not authenticate a provider or financial action.
    """
    payment = PaymentIntent.model_validate(payment.model_dump(warnings=False))
    if expected_state is not None:
        expected = TypeAdapter(PaymentState).validate_python(expected_state)
        if payment.state != expected:
            raise StalePaymentState("Payment state changed; reload before transitioning.")
    target = transition_state(payment.state, event)
    return PaymentIntent.model_validate(payment.model_dump() | {"state": target})
