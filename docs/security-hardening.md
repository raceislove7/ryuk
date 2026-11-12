# Historical hardening record

Preserved from b263e05. Current merged validation is in STATUS.md: 1,056 backend tests and 44 mocked browser assertions. Historical counts below do not supersede that result.

# Step 12 — security review (2026-11-11)

## Scope and provenance

Reviewed the actual latest GitHub baseline **674bdf0**, including session/provisioning, parser/workspace APIs, policy/digest/approval services, checkout store/coordinator, PayPal adapter, Next proxy/UI/SDK and test-only startup. A previously supplied review summary mentioned 1,004 tests and D-033, but its changes/report were absent from this checkout and origin/main. Those numbers/findings are not treated as verified evidence. This report describes the independently reviewed changes in this commit. No live provider/model/payment requests or existing ledger resets were performed.

## Confirmed High findings — fixed or contained

### H1: Unauthenticated model consumption
- A caller could POST /v1/agent/parse directly, bypassing the authenticated workspace wrapper, reaching a paid model without a session. The Next proxy allowlist did not remove the direct backend route.
- Fix: authentication/origin dependency runs before parsing. Model requests have a bounded single-buyer 10/minute allowance; status/payment recovery is not rate-limited by that model allowance. Both parser entry points enforce it.
- Regression: anonymous calls never invoke the parser; authenticated model-limit exhaustion leaves workspace/status available. Browser test checks direct anonymous API refusal.

### H2: Incomplete extraction could bypass requirement review
- A valid structured model extraction could omit or weaken a user requirement while still producing a deterministic PASS and below-threshold ALLOW. Schema/source checks do not prove semantic completeness.
- Containment: every model-derived workspace proposal requires explicit application review, even below the price threshold. The dialog compares the original request with the full parsed intent. Proposal digest v2 binds both, plus the review marker and prior canonical terms/snapshot. Approval remains owner/expiry/policy bound; deterministic FAIL cannot be overridden.
- Regression: all non-denied workspace candidates require review; pre-approval checkout is blocked; changing the review marker changes the digest. Browser tests explicitly approve the original/parsed terms before payment.
- Limit: this prevents automatic review bypass, **not semantic incompleteness or inattentive human approval**. No automatic confidence score certifies complete intent preservation.

### H3: Input/error reflection
- Invalid login/body fields could appear in FastAPI validation responses. A parser clarification exception could expose its message through the public API, including arbitrary provider/credential-like content if raised by an adapter.
- Fix: validation responses use a fixed message without input/context/field values. Clarification messages are fixed; provider/financial errors remain sanitized. No values are inspected to redact them heuristically.
- Regression: oversized/nested/extra secret-bearing synthetic inputs and clarification exceptions do not echo sentinel values.

### H4: HTTPS could issue insecure session cookies
- HTTPS origins combined with RYUK_SECURE_COOKIES=false were accepted. The session cookie could then be transmitted on insecure requests to the same host in a misconfigured deployment.
- Fix: provisioning and session construction reject HTTPS/insecure-cookie combinations. Explicit insecure cookies remain permitted only for validated local HTTP development origins through provisioning. HttpOnly/SameSite and origin checks remain enforced.
- Regression: HTTPS configuration requires secure cookies; local test settings remain functional.

No Critical issue was confirmed within this review. This is not a proof that none exists.

## Additional completed hardening

- Bounded session allocation and login-client buckets; separate model-call limits.
- Bounded streaming Next request bodies before buffering more than 64 KiB.
- Clickjacking/frame, object/base, MIME-sniffing and referrer headers, compatible with the PayPal SDK. Browser assertions check headers/origin/body/path behavior.
- Test reset server now requires explicit RYUK_E2E_TEST_ONLY=1 and always creates a fresh temporary ledger. It cannot target an existing financial database via its prior DB override. It is not copied into production images.
- Read-only consistent operator SQLite backup command with exclusive new mode-0600 output, overwrite/symlink refusal and integrity check. Fresh-fixture rehearsal preserves held/settled totals. See operations.md.
- Restored the previously implemented backend-only Groq structured parser support onto the newer repository implementation; real-SDK HTTP mocks share the existing schema/source/domain validation and authentication boundary.

## Residual risks — not production acceptance

### Medium R1: Volatile canonical authority and early audit
Sequence: restart or route a session/proposal to a different worker; in-memory sessions, canonical proposals/approvals and early events disappear or disagree while durable payment/holds remain. Current behavior blocks new capture without authority; provider uncertainty recovery uses durable original terms. Availability and audit completeness remain limited.
Recommendation: use one private worker now; before multi-user/multi-worker deployment, persist canonical authority/audit with transactional ownership and versioning (prefer PostgreSQL). Rehearse restart/recovery, never rebuild consent from browser JSON.

### Medium R2: Unresolved provider creates/long-lived uncertainty
Sequence: create times out before an order ID is durably recorded, or capture queries remain inconclusive. Holds/blocked attempts can remain indefinitely. Releasing by elapsed time or creating another purchase can duplicate external effects.
Recommendation: operator reconciliation through PayPal records/support with exact original request/reference IDs; preserve holds and audit. Automated orphan resolution needs verified provider semantics and a dedicated workflow. Do not invent a reset/retry command.

### Medium R3: Demo authentication is not a public identity/availability layer
Sequence: anonymous callers exhaust the shared proxy login allowance, disrupting the one buyer; or multiple workers each maintain independent limits/sessions. Compromise of the shared demo password grants that one configured buyer's authority. Bounds reduce memory/cost exposure but do not supply distributed abuse prevention or individual accountability.
Recommendation: keep the demo private/single-worker, apply trusted edge throttling/TLS, rotate the password to invalidate sessions, and deploy real user identity/revocation plus distributed rate limits before public operation. Never trust arbitrary X-Forwarded-For values to bypass limits.

### Low R4: Development dependency advisories
Production npm audit is clean. Development tooling advisories remain in the current lockfile. An attacker-controlled development input may affect tooling availability; this is not evidence of a reachable production payment exploit.
Recommendation: review compatible tooling upgrades separately; do not force a major lockfile rewrite or claim advisories fixed without validation. Record current audit counts in STATUS.md.

### Low R5: Full script CSP and external SDK trust
Frame/object/base restrictions are now present, but nonce-based script restrictions/SRI isolation are not. A future script-injection bug or compromised third-party SDK could affect the signed-in browser. React escaping and financial backend checks remain essential; no current XSS exploit was confirmed.
Recommendation: design and test nonce-based CSP with PayPal's dynamic script/frame/connect requirements and monitor SDK dependencies. Do not deploy an untested restrictive policy that silently breaks buyer approval.

## Evidence

Backend suite, frontend lint/typecheck/production build, committed mocked browser suite, dependency audits and isolated Docker checks are recorded with actual results in STATUS.md. Tests cover ownership, expiry, replay, tampering, duplicates, concurrent reservations, provider spoofing, cancellation and query-only ambiguity recovery. Financial provider behavior is mocked. Live buyer-approved Sandbox capture and live model semantic acceptance remain unverified.
