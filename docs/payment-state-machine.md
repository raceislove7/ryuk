# Payment state machine

`app.services.payment_state_machine` centrally validates payment transitions. It is a provider-neutral, side-effect-free library: no PayPal/OpenAI client, URLs, capture calls, network requests, clocks, database writes, or financial decisions. The requested legacy state name AWAITING_PAYPAL_BUYER is retained, but the implementation has no PayPal dependency.

The canonical vocabulary is exactly CREATED, POLICY_CHECK, AWAITING_APPROVAL, CHECKOUT_READY, AWAITING_PAYPAL_BUYER, CAPTURE_PENDING, SUCCEEDED, FAILED, and PENDING_PROVIDER. The unused VERIFYING member from the earlier planning/schema stage is removed; it is rejected rather than silently migrated. No payment database exists in this repository.

## Legal transitions

| Current state | Trusted backend event | Next state |
| --- | --- | --- |
| CREATED | START_POLICY_CHECK | POLICY_CHECK |
| CREATED | CANCEL | FAILED |
| POLICY_CHECK | POLICY_REQUIRES_APPROVAL | AWAITING_APPROVAL |
| POLICY_CHECK | POLICY_ALLOWED | CHECKOUT_READY |
| POLICY_CHECK | POLICY_DENIED or CANCEL | FAILED |
| AWAITING_APPROVAL | APPROVAL_RECORDED or RECHECK_POLICY | POLICY_CHECK |
| AWAITING_APPROVAL | APPROVAL_REJECTED or CANCEL | FAILED |
| CHECKOUT_READY | START_BUYER_APPROVAL | AWAITING_PAYPAL_BUYER |
| CHECKOUT_READY | RECHECK_POLICY | POLICY_CHECK |
| CHECKOUT_READY | CANCEL | FAILED |
| AWAITING_PAYPAL_BUYER | REQUEST_CAPTURE | CAPTURE_PENDING |
| AWAITING_PAYPAL_BUYER | RECHECK_POLICY | POLICY_CHECK |
| AWAITING_PAYPAL_BUYER | BUYER_DECLINED or CANCEL | FAILED |
| CAPTURE_PENDING | CAPTURE_CONFIRMED | SUCCEEDED |
| CAPTURE_PENDING | CAPTURE_FAILED | FAILED |
| CAPTURE_PENDING | CAPTURE_UNCERTAIN | PENDING_PROVIDER |
| PENDING_PROVIDER | RECONCILED_SUCCESS | SUCCEEDED |
| PENDING_PROVIDER | RECONCILED_FAILURE | FAILED |
| SUCCEEDED / FAILED | None | Terminal |

Every other state/event combination is illegal. Same-state transitions are also rejected. Application approval returns to POLICY_CHECK rather than skipping current policy, expiry, and binding checks. Before capture starts, an invalidation can return checkout/buyer-waiting states to policy; after capture may be in flight, ordinary cancellation or policy denial cannot pretend it failed.

## API

- `allowed_transitions(state)` returns an immutable target set for introspection.
- `can_transition(current_state, target_state)` reports one-step structural reachability, not financial permission.
- `transition_state(current_state, event)` resolves an event through the central immutable table or raises IllegalPaymentTransition.
- `transition_payment_intent(payment, event, expected_state=...)` revalidates the input and returns a new validated PaymentIntent with only its state changed. All user/proposal/offer/merchant/money/currency/policy/verification/digest/approval metadata, creation time, payment ID, and idempotency key remain unchanged. The input is not mutated.

The optional expected_state check raises StalePaymentState if the supplied current record differs from what the caller expected. It is a local check, not a database compare-and-swap. Unknown enum values, arbitrary target-state strings used as events, removed VERIFYING, and malformed/coercible model fields fail validation. Both levels of the transition table are immutable.

## Provider uncertainty and terminal states

An ambiguous capture outcome becomes PENDING_PROVIDER, never an assumed failure or success. That state has no capture-retry, cancellation, reset, or generic CAPTURE_FAILED path. It remains pending until trusted reconciliation supplies a conclusive success/failure event. A timeout/exception is not CAPTURE_FAILED or RECONCILED_FAILURE. The current uncertainty path covers capture; earlier order-creation recovery belongs to the later adapter/coordinator and must never imply successful payment.

SUCCEEDED and FAILED cannot be reopened/reset or transitioned to themselves. Repeated provider notifications should be deduplicated against durable stored state by the future event handler, rather than creating a second transition or capture. This module does not generate new payment attempts or change idempotency keys to permit a retry.

## Authority and integration boundary

Events must originate from trusted backend coordination and verified provider observations, never an LLM, browser-submitted state, unverified webhook, or free-text instruction. CAPTURE_CONFIRMED / RECONCILED_SUCCESS only describe an already established provider outcome; valid event spelling does not prove that outcome. A schema-valid deserialized PaymentIntent is likewise data, not authority. No public transition endpoint or model tool is exposed.

This library enforces graph legality only. It does not authenticate events, verify buyer consent, apply financial policy, load current canonical proposals, reserve money, or call a provider. The future checkout coordinator must invoke the existing canonical/approval/policy revalidation gates, enforce atomic reservations and duplicate/idempotency controls, and obtain provider buyer approval before REQUEST_CAPTURE. All authoritative state changes must use this centralized table and be persisted conditionally/atomically with audit events. Financial/context metadata updates must be verified separately before the state update.

The PayPal adapter, durable state store, transactional coordinator, audit persistence, HTTP wiring, and real provider execution remain later stages. No live payment or success assertion is performed by the implementation tests.
