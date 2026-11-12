# PayPal Sandbox adapter

`backend/app/services/paypal.py` is internal backend code, with no public routes,
LLM tools, browser secrets, automatic startup calls, or live-provider test calls.
Use `PayPalSettings.from_env()` and `async with PayPalSandboxAdapter(settings)`.
Docker Compose passes the four `PAYPAL_*` server settings only to the backend.
Missing credentials do not prevent health/catalog startup. Configure private server
environment variables for local Python execution; the adapter does not load dotenv.
Only `sandbox` and exactly `https://api-m.sandbox.paypal.com` are accepted.
Redirects are disabled; TLS verification stays enabled. Credentials and tokens use
SecretStr, OAuth tokens are cached with a 30-second expiry margin and refresh lock,
and errors omit provider bodies, raw transport exceptions, and credentials.

## Interface and caller responsibilities

- `create_order(terms, idempotency_key=...)` creates one CAPTURE purchase unit.
- `get_status(order_id, terms, capture_attempted=True)` reconciles an attempted capture.
- `capture(order_id, terms, idempotency_key=...)` first performs an authenticated GET,
  verifies exact terms and provider APPROVED status, then posts capture once.
- `PayPalOrderTerms` requires a backend internal payment reference, the actual
  supported Sandbox payee merchant ID, a positive strict integer amount, and USD/EUR.
  Formatting uses integer division only. Other currencies fail explicitly; no FX or
  assumptions about zero-decimal currencies are made.

The coordinator must resolve canonical terms and a supported demo merchant mapping.
Synthetic hotel merchant IDs are not PayPal merchant IDs. Do not silently remap an
approved merchant or claim arbitrary-merchant payments. The adapter requires exact
returned payee, reference, currency and amount matching, including capture amount.
It rejects AUTHORIZE, multiple purchase units/captures, malformed amounts and IDs.

Before calling capture the future authenticated coordinator must recheck current
policy, bound proposal, unexpired application consent, budget reservation, and
persistent duplicate history. PayPal buyer approval is an additional requirement.
No public capture route, financial authorization, storage, audit, budget reservation,
checkout UI, or durable state transaction is implemented in this adapter stage.

## Idempotency and uncertain outcomes

`request_id(operation, internal_key)` derives a deterministic UUID with separate
create/capture namespaces. Persist the internal key, immutable terms, operation,
provider request ID and returned order ID before advancing execution. Reuse keys
for the same operation only. The adapter does not generate random retry keys.
Provider idempotency is time-limited, not permanent application duplicate protection.
The coordinator still needs a durable unique key and execution lock across processes.

OAuth failure occurs before mutation dispatch. A mutation timeout, HTTP error
(including 4xx), malformed JSON or invalid returned binding raises sanitized
`PayPalUncertain` with order ID if known and the stable provider request ID. It
never automatically retries. This conservative classification may require operator
review even for ordinary validation refusals; an HTTP error alone is not proof of
an authoritative terminal payment failure. GET errors preserve existing state.

Persist uncertainty and query `get_status(..., capture_attempted=True)` before any
further action. Open APPROVED/CREATED results do not prove capture failure and must
remain PENDING_PROVIDER. The adapter also remembers uncertain captures in memory
and blocks further capture while reconciliation is inconclusive. This guard is
not durable: a new adapter/process must load the coordinator's persisted state and
must never call capture on PENDING_PROVIDER. The state machine allows only conclusive
reconciliation events to exit that state. Already confirmed terminal preflight
results return without issuing another capture POST.

An uncertain create can have no known order ID. There is no invented lookup API by
request ID: preserve that key, stop checkout, and implement an operator/recovery
procedure with verified provider retention guarantees before an explicit create
retry. No automatic create recovery or retry is implemented here.

## Provider observations

These are authenticated provider observations, not assignments to PaymentIntent.
The coordinator must emit legal state-machine events and atomically persist audit.

| Provider evidence after exact binding checks | Observation |
| --- | --- |
| CREATED / SAVED / PAYER_ACTION_REQUIRED / APPROVED, no capture attempted | AWAITING_PAYPAL_BUYER; only APPROVED sets buyer_approved |
| Open order after capture was attempted | PENDING_PROVIDER |
| COMPLETED order + exactly one full-amount final COMPLETED capture | SUCCEEDED |
| One exact-amount DECLINED / FAILED capture, or VOIDED order without captures | FAILED |
| PENDING / refunded / partial / unknown capture, missing capture on COMPLETED, unknown order | PENDING_PROVIDER |
| Wrong reference/merchant/amount/currency/order ID/intent, malformed shape | Error; never success |

COMPLETED order by itself is not proof funds were captured. Refund lifecycle and
partial capture support are outside this MVP. Browser callbacks and webhook strings
are never accepted as provider truth by this module. Buyer navigation/cancellation
and UI links are deferred to checkout integration.

## Verification and sources

84 mocked-HTTP/mapping/configuration cases cover OAuth caching/expiry/concurrency,
errors, stable operation IDs, exact integer conversion, binding tampering, provider
states, buyer preflight, terminal deduplication, redirects, malformed JSON, ambiguous
mutation failure, GET reconciliation, and secret-safe errors. Tests use the actual
httpx2 client with MockTransport. They establish no live Sandbox acceptance.

Implementation semantics were checked against official PayPal references:
[OAuth](https://developer.paypal.com/api/rest/authentication/),
[Orders v2](https://developer.paypal.com/api/orders/v2),
[Orders schema](https://developer.paypal.com/api/orders/v2/schema.json),
[idempotency](https://developer.paypal.com/api/rest/reference/idempotency/), and
[currencies](https://developer.paypal.com/api/codes/currency).

Stage 10 integration: [checkout coordination](checkout.md) now supplies the adapter’s synchronous `before_capture` gate after preflight/OAuth and before POST. It provides durable original terms/keys, reservations, state/audit and GET-only recovery. Direct adapter calls do not acquire financial authority; public routing remains disabled until real authentication and service provisioning.
