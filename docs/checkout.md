# Checkout integration

Stage 10 connects canonical proposal/approval and policy to the real Sandbox
adapter, with durable checkout state, budget reservations and audit. All provider
acceptance in this stage is mocked HTTP; no live payment was performed.

## Backend flow

1. A trusted server caller supplies a canonical proposal ID and authenticated actor.
   `CheckoutService.create_checkout` reloads the owned proposal, current SQLite
   policy/budget, current approval and regenerated digest through the existing
   approval service. Policy must allow checkout. The server resolves a configured
   supported Sandbox merchant mapping; browser/model terms are never arguments.
2. One durable checkout per proposal is created, with stable internal payment/key,
   exact proposal binding and immutable provider terms. Its create-dispatch audit
   commits before Orders v2 POST. Retries/concurrent calls return the same record,
   including CREATING/UNKNOWN records; they do not issue a second create request.
3. A successful create stores the provider order ID and enters AWAITING_PAYPAL_BUYER.
   The frontend stage must pass that ID to the PayPal SDK for real buyer approval.
   Application consent and PayPal buyer consent remain independent gates.
4. A capture action accepts only the internal checkout ID. The adapter fetches the
   stored PayPal order, verifies exact reference/payee/amount/currency and APPROVED
   status, and obtains OAuth before invoking the synchronous final dispatch gate.
5. That gate opens a SQLite `BEGIN IMMEDIATE` transaction, reloads current proposal,
   verification/digest, latest approval ownership/expiry and policy/budget, and
   checks equality to the original payment/provider bindings and merchant mapping.
   It atomically reserves the full integer amount, commits legal state transitions
   to CAPTURE_PENDING, and writes revalidation/reservation/request-ID audit events.
   Canonical approval locks remain held until commit. No database/approval lock
   spans network I/O. Another checkout sees the hold when evaluating availability.
6. Only then can the adapter dispatch one capture POST with the persisted key.
   Confirmed success moves the hold to settled spending once; verified failure
   releases it once. Uncertainty keeps the hold and enters PENDING_PROVIDER.

The commit is the authorization/dispatch linearization point. Changes detected
before it block capture; later revocation cannot undo an already committed dispatch.
Proposal updates cannot silently change an existing checkout. Changed or replaced
approval references require a fresh proposal/checkout, rather than reusing an old
order or reviving a previous grant. Reservations are created at capture, not while
the user is browsing PayPal, so policy/budget may legitimately block a later capture.

## Recovery and accounting

`capture` on CAPTURE_PENDING/PENDING_PROVIDER performs reconciliation only.
`reconcile` queries the provider against persisted original terms, even after
proposal/policy changes or loss of in-memory approvals. It never retries capture.
An open APPROVED order after a capture attempt is inconclusive: retain the hold.
GET errors retain uncertainty and append a safe audit event. Definitive success
settles the original amount; failure releases it; repeated/concurrent observations
cannot settle twice. A canceled task after dispatch claim also retains its hold.

A crash between claim commit and POST is deliberately conservative: recovery queries
provider status; it cannot safely infer that dispatch did not occur. There is no
TTL that silently releases an uncertain hold. Operator/provider recovery is needed
if the provider never supplies conclusive evidence. Unknown create outcomes and
orphaned CREATING records stop checkout; there is no automatic create retry or
invented lookup-by-request-ID API. Their separate order_creation flag must be
shown alongside payment state, not mistaken for successful checkout readiness.

A terminal preflight observation emits no POST. If an external actor already
captured the exact stored order, the ledger records that confirmed debit and an
EXTERNAL_CAPTURE_DISCOVERED event, even when current policy would deny new spending.
This is accounting for observed provider truth, not authorizing another payment.
A local cancel only stops AgentPay capture before dispatch; it is not a PayPal
void API, and cannot cancel an uncertain/in-flight capture. Refunds, external
merchant activity after a local terminal result and continuous provider monitoring
require separate operator/reconciliation support.

## Persistence and provisioning

`CheckoutStore(path)` uses Python's built-in SQLite with WAL, FULL synchronous
transactions, a unique proposal constraint and reservation primary keys. Use an
explicit persistent **local** file path; `:memory:` is rejected. Database files
and WAL/SHM sidecars are ignored by Git, and the database is created mode 0600.
Protect the containing directory and backups as private application data.

Trusted backend bootstrap must:

- Create accounts using `store.create_account(BudgetSnapshot(...))`; importing
  reservations is forbidden. `set_budget_limit` preserves settled spending/holds.
- Persist current `FinancialPolicy` using `put_policy`.
- Configure supported canonical merchant -> actual PayPal Sandbox payee mappings
  using `map_merchant`. Never map arbitrary hotel merchants without a supported
  demo relationship; all hotel fixtures remain synthetic, not real bookings.
- Register canonical proposals and record required buyer application consent in
  `InMemoryApprovalService` through its existing backend operations.
- Construct `PayPalSandboxAdapter(PayPalSettings.from_env())` and `CheckoutService`.
  Manage the adapter's async lifetime at server startup/shutdown.

This ledger is a reproducible single-host reference, with no new dependencies or
PostgreSQL service. PostgreSQL remains preferred for a production deployment.
Multiple SQLite connections/processes serialize financial claims, but canonical
proposal/approval authority is still the existing in-memory service. This is not
a fully durable multi-worker authority deployment. Losing it blocks new capture;
existing uncertain attempts can still reconcile from durable original terms.
A durable canonical authority/authentication implementation remains a blocker for
public deployment. Do not reconstruct consent from a browser-held approval object.

## HTTP contract and authentication boundary

The registered routes are:

| Action | Request |
| --- | --- |
| Create | `POST /v1/checkouts` with `{"proposal_id":"..."}` |
| Read | `GET /v1/checkouts/{checkout_id}` |
| Process buyer callback | `POST /v1/checkouts/{checkout_id}/capture` with `{}` |
| Reconcile | `POST /v1/checkouts/{checkout_id}/reconcile` with `{}` |
| Cancel before capture | `POST /v1/checkouts/{checkout_id}/cancel` with `{}` |

Responses include server-owned display amount/currency/merchant, internal checkout
ID, state, order_creation and PayPal order ID. They exclude credentials, tokens,
operation keys, user identity and approval authority records. Extra JSON fields
(including amount, merchant, user, approval, status and order IDs) are rejected.

Routes **return 503 by default**. A trusted backend integration must install a real
session/token verifier for `get_checkout_actor` and provision `app.state.checkout_service`.
The authentication dependency accepts no unsigned identity header or browser JSON
user ID. FastAPI dependency overrides provide the integration seam; constant actors
are used **only in tests**, never as a public authentication implementation.
Ownership failures return 404, failed gates 409 and unavailable storage/provider
operations 503 with safe messages. Health/catalog remain usable without checkout
configuration. The frontend and actual session integration are not implemented here.

## Verification

Run `cd backend && .venv/bin/pytest -q tests/test_checkout.py`.
49 new tests connect current catalog/verifier/policy/approval, SQLite and the actual
PayPal HTTP adapter with MockTransport. They cover eligible/review paths, independent
buyer consent, source changes during GET, expired/superseded approvals, forged
fields/digests/provider bindings, ownership, durable retries, concurrent create and
capture, reserved-funds contention, atomic rollback, cancellation, restart recovery,
original-term reconciliation, accounting, API flow and fail-closed default auth.
They establish mock integration correctness, not live PayPal or complete browser E2E.

Stage 11 now supplies the opt-in single-buyer private session, runtime provisioning and buyer casebook; see [frontend integration](frontend.md). Default mode remains disabled and production multi-user/durable canonical authority is still pending. Live acceptance has not been established.
