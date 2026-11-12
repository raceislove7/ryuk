# AgentPay Architecture

## Design principle

AgentPay separates **reasoning** from **authority**.

```text
Probabilistic:
User language -> LLM intent -> ranking -> explanation

Deterministic:
Verification -> policy -> approval -> budget reservation -> payment state machine

Provider:
PayPal create/approve/capture/status
```

## Components

### Frontend
Collects intent, shows shortlist/evidence, collects approval, starts PayPal buyer approval, displays verified status and audit trail.

The browser is not trusted for amount, merchant, policy decision, or payment success.

### Intent Parser
Raw request -> typed PurchaseIntent.
LLM output must pass schema validation.

### Offer Catalog
Trusted fixture data or approved external APIs.
Offers include merchant ID, price, currency, attributes, evidence, and source.

### Verification Engine
Compares PurchaseIntent with Offer.
Returns required checks, preference score, missing evidence, and PASS/FAIL/UNKNOWN.

### Policy Engine
Pure deterministic service.
Inputs include intent, offer, verification, budget, policy version, merchant state, and approval.
Outputs DENY / REQUIRE_APPROVAL / ALLOW_ELIGIBLE_FOR_CHECKOUT.

### Approval Service
Approval is user-specific, proposal-specific, amount-specific, merchant-specific, and expiring.
Any bound field change invalidates approval.

### Budget Reservation
Reserve before irreversible action.
Available budget = limit - settled - active_reservations.

### Payment State Machine

```text
CREATED
POLICY_CHECK
AWAITING_APPROVAL
CHECKOUT_READY
AWAITING_PAYPAL_BUYER
CAPTURE_PENDING
SUCCEEDED
FAILED
PENDING_PROVIDER
```

PENDING_PROVIDER exists because timeout != confirmed failure. The centralized event-driven transition graph is implemented in `backend/app/services/payment_state_machine.py`; SUCCEEDED/FAILED are terminal, and uncertain capture only resolves through verified reconciliation events. See `docs/payment-state-machine.md`. State legality does not establish provider truth or authorize capture.

### PayPal Adapter
Only this adapter knows PayPal URLs, OAuth, create order, capture, and provider mapping.

### Audit events

```text
INTENT_CREATED
OFFER_SELECTED
VERIFICATION_COMPLETED
POLICY_ALLOWED
APPROVAL_REQUESTED
APPROVAL_GRANTED
BUDGET_RESERVED
PAYPAL_ORDER_CREATED
PAYPAL_BUYER_APPROVED
CAPTURE_REQUESTED
CAPTURE_CONFIRMED
PAYMENT_FAILED
PROVIDER_STATE_RECONCILED
```

## Proposal digest

Canonical versioned payload includes:
- format version
- proposal_id
- created_at normalized to UTC
- user_id
- offer_id
- merchant_id
- amount_minor
- currency
- policy_version
- verification_snapshot_id
- intent_review_required (backend-owned; all model-derived workspace proposals)

Serialize compact sorted-key JSON and SHA-256 it using `agentpay-proposal-v2`; bind approval to the hash. Validate the current verification snapshot first.
Before checkout/capture, regenerate and compare.

`proposal_binding.py` and `InMemoryApprovalService` implement this binding and the internal approval lifecycle. Canonical updates invalidate outstanding grants permanently; expiry, current-request ownership, and current financial policy are rechecked. The canonical reference store is process-local. Checkout now uses it for a final authority gate, while a SQLite ledger persists payment claims, holds and audit. Identifier-only checkout HTTP routes fail closed until trusted authentication/service provisioning. Durable canonical approval storage remains pending. See `docs/approvals.md`.

## Threat model

### Prompt injection
Listing text is data, not instruction. LLM cannot pay.

### Amount tampering
Backend reloads amount from canonical offer.

### Merchant substitution
Approval binds merchant and proposal digest.

### Duplicate payment
Stable idempotency key + unique attempt.

### Concurrent overspend
Atomic budget reservation.

### Provider timeout
Move to PENDING_PROVIDER and query provider state before any retry.

### Fake verification
Semantic PASS requires evidence. Missing evidence -> UNKNOWN.

## Why not multi-agent first?

One orchestrated workflow is easier to test, debug, secure, and demo.
If subagents are added, they still produce proposals only.
Financial authority remains outside all agents.

## Checkout integration reference

`CheckoutService` connects canonical approval/policy to the Sandbox adapter. `CheckoutStore` uses a private local SQLite file for durable execution records, unique proposal claims, budget holds and checkout audit, with a final reload/digest/approval/policy/reservation gate immediately before capture dispatch. Reconciliation uses original stored terms and never retries capture. SQLite is a single-host reference; PostgreSQL remains preferred, and canonical proposal/approval authority is still process-local. Public routes require real authentication and trusted provisioning. See `docs/checkout.md` and D-029.

## Ryuk frontend integration

The visible product is Ryuk. A Next same-origin allowlist proxy connects its casebook to thin authenticated workspace/proposal/approval/audit endpoints. An explicitly enabled private single-buyer demo session uses backend password verification and an opaque HttpOnly cookie; no browser identity header authenticates. Runtime provisioning is off by default and seeds an account/policy only once, preserving the ledger. The frontend displays backend intent/evidence/policy and passes only proposal/payment identifiers into the existing checkout flow. The actual PayPal JS v5 SDK handles buyer authorization; only a backend-confirmed capture displays success. Canonical authority remains process-local and the single-host SQLite execution ledger is unchanged. Production multi-user identity, durable canonical storage and live provider acceptance remain pending; see `docs/frontend.md`, D-030 and D-031.

Step 12 requires exact application intent review for every model-derived workspace
proposal, even below the requested review threshold. The existing approval service
binds original/parsed intent via its verification snapshot and the backend-owned
review flag via digest v2; deterministic policy rechecks this at checkout/capture.
This contains incomplete extraction, not a proof of semantic fidelity. Direct parser
HTTP calls now require the same private session/origin gate before provider creation;
validation responses never reflect inputs and HTTPS requires Secure cookies. See
`docs/security-review.md` and D-033. Financial claims/recovery still use the same
SQLite ledger; no financial reset or migration was performed.
