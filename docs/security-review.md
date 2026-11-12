# Step 12 — security review

Merge repair verified 2026-11-12: current combined evidence is 1,056 backend tests and 44 mocked browser assertions; see STATUS.md. Historical review evidence below is retained. Live buyer acceptance remains unverified.

Reviewed 2026-11-11 from clean commit `674bdf0`, then applied the fixes below.
Findings reference **pre-fix lines at that commit** unless explicitly identified
as new code. Severity reflects impact with the stated preconditions, not an assertion
that this private, loopback-bound Sandbox demo is publicly deployed.

## Findings first — confirmed High issues

### H-01 — High: unauthenticated billable parser
- **Location:** `backend/app/api/agent.py:24-47`; `backend/app/main.py:32`.
- **Sequence:** with a configured model, call `POST /v1/agent/parse` directly without
  the opaque session. The parser dependency initializes and invokes the provider.
  Repeat requests to consume quota outside the authenticated workspace.
- **Impact/preconditions:** unauthorized model expense and service/quota exhaustion;
  attacker must reach the backend and the operator must configure a real model.
  Compose's loopback binding and the Next allowlist restrict exposure, but do not
  authenticate this backend endpoint. This is not an unauthorized PayPal capture.
- **Evidence:** isolated fake parser returned 200 to an unauthenticated request;
  the regression expecting 401 failed before the fix. No live provider call.
- **Fix:** add a separate authenticated HTTP wrapper, resolving the existing session
  and mutation-origin gate before parser initialization. Internal workspace reuse
  calls the side-effect-limited parsing helper, not a public unauthenticated route.
- **Regression:** `test_direct_parser_requires_authentication_before_provider_initialization`,
  unsigned Bearer/user-header rejection across private routes, and authenticated
  direct-parser requests with absent/forged/wrong-scheme origins. Existing SDK-mock
  API contract tests explicitly override the actor only in tests.
- **Disposition:** fixed. Authorized model calls still need resource/quota controls (M-01).

### H-02 — High: incomplete extraction can bypass intent review
- **Location:** `backend/app/services/intent_parser.py:147-161,190-217`;
  `backend/app/services/workspace.py:79-88`; `frontend/app/page.tsx:776-797`.
- **Sequence:** the user's instruction says "Gym mandatory". Malformed/adversarial
  model output moves gym to preferences but quotes only "Gym", or omits a required
  amenity entirely. Role validation examines only supplied quotes; verification
  checks only remaining attributes. A below-threshold offer can appear eligible
  without application review of the changed interpretation. Buyer approval in
  PayPal confirms financial terms, not omitted hotel requirements.
- **Impact/preconditions:** purchasing an offer inconsistent with mandatory intent,
  or silently changing preference semantics. Requires a bad/injected model response
  and a buyer proceeding through checkout. Active financial caps and PayPal buyer
  authorization are not bypassed; no model can directly capture.
- **Evidence:** a gold extraction with mandatory gym moved to preferences and its
  quote shortened to "Gym" passed the original validation; the new rejection test
  failed. Omission checks demonstrate that remaining verification alone is not a
  completeness proof. No assertion about live model susceptibility is made.
- **Fix/containment:** check the enclosing source clause for explicit role wording.
  More importantly, trusted workspace orchestration marks **every** model-derived
  proposal as requiring human intent review. Pure policy adds `INTENT_REVIEW_REQUIRED`;
  the existing owned, expiring approval service resolves it only with exact consent.
  Proposal digest v2 binds this flag in addition to the intent-bearing verification
  snapshot. Checkout/capture rerun that policy and binding. The approval dialog shows
  original instruction, required/preferred values, quantity, budget and requested
  threshold, instructing the buyer to reject omissions/changed meaning.
- **Regression:** shortened quote rejection; gym/private-pool omissions cannot create
  checkout before review and rejection cannot pay; changing the review flag breaks
  the digest and invalidates old consent; browser suite checks review before SDK
  mounting and original/parsed terms in the dialog. Existing hard-denial, expiry,
  replay and changed-intent/capture tests still apply.
- **Disposition:** automatic review bypass fixed; semantic completeness is **not**
  solved. Human oversight and unsupported/ambiguous language remain M-02.

### H-03 — High: submitted credentials reflected in validation errors
- **Location:** `backend/app/api/workspace.py:21-22`; default validation handler in
  `backend/app/main.py:30`; `frontend/app/api/ryuk/[...path]/route.ts:56-68`.
- **Sequence:** submit an overlong password, an object containing a password marker,
  or a credential-bearing extra field. Default FastAPI validation returns original
  `input` and validator context; the Next proxy forwards that JSON to the browser.
- **Impact/preconditions:** private submitted material unnecessarily reaches response
  bodies, browser network history and response-capturing diagnostic systems. Requires
  invalid sensitive input and access to such diagnostics to expose it beyond the
  submitter. No cross-user credential retrieval was demonstrated.
- **Evidence:** three synthetic credential-marker cases were reflected before the
  fix, including the extra field and wrong-type object.
- **Fix:** application-wide request-validation handler returns a fixed 422 message,
  omitting raw input, attacker-controlled field names, validator context and errors.
  Errors are not logged by this handler. Provider failures remain separately sanitized.
- **Regression:** three direct-backend cases; actual production-Next proxy validation
  response contains no synthetic credential marker. Malformed JSON/extra fields
  remain rejected, not ignored.
- **Disposition:** fixed. No user's secret values were read or scanned.

### H-04 — High, configuration-dependent: insecure remote session cookie
- **Location:** `backend/app/services/provisioning.py:46-49`;
  `backend/app/api/workspace.py:73-80`.
- **Sequence:** configure a remote HTTPS app origin with `RYUK_SECURE_COOKIES=false`.
  Startup accepts it and issues an opaque session cookie without Secure. Subsequent
  HTTP use on that host can transmit it to an on-path attacker, who can replay the
  session with the expected Origin. SameSite and origin checks do not authenticate
  a non-browser replay of a stolen token.
- **Impact/preconditions:** private-workspace session compromise; requires unsafe
  operator configuration, HTTP use and network interception. Separate PayPal buyer
  approval is still needed for a new capture; application consent/data are exposed.
- **Evidence:** isolated startup accepted remote HTTPS with insecure cookies before
  the fix. The regression expecting refusal failed. No cookie theft experiment.
- **Fix:** reject false unless the validated origin is local HTTP; reject before
  database provisioning. HTTPS must use Secure cookies.
- **Regression:** remote HTTPS/false rejected; HTTPS/true and HTTP loopback/false
  startup cases pass; existing cookie expiry/logout/forgery tests pass.
- **Disposition:** fixed. HTTPS termination and private network/ACL configuration
  remain operator responsibilities.

No confirmed Critical finding. Six failing pre-fix assertions reproduced these
four findings; the original full backend suite was independently rerun: **983 passed**.

## Remaining Medium findings / deployment limitations

### M-01 — Medium: unbounded request buffering and authorized resource use
- **Location:** `frontend/app/api/ryuk/[...path]/route.ts:26-30`;
  `backend/app/api/workspace.py:115-128`; `backend/app/services/workspace.py:22,71-116`;
  `backend/app/services/session.py:24,30-44`.
- **Sequence:** send a huge/slow login body to Next, which reads it fully before
  enforcing 64 KiB; directly send oversized backend JSON. An authenticated user can
  repeatedly parse and retain six/eight proposals and events without lifecycle caps.
  The login limit shares the proxy's backend client IP, allowing remote users to
  exhaust another user's login window. Successful sessions are not capped.
- **Impact/preconditions:** memory/connection/quota exhaustion and login denial of
  service. Body buffering is unauthenticated on the allowlisted session route;
  sustained model/proposal growth requires valid private credentials. Memory/CPU
  exhaustion load thresholds were not measured.
- **Fix/test:** stream a strict byte limit before buffering at proxy and backend,
  enforce ingress connection/body timeouts, bounded authenticated parser concurrency
  and quota, and canonical/session retention caps. Use a trusted proxy-aware limiter,
  never unsigned X-Forwarded-For. Test chunked oversized bodies, bounded allocation,
  independent real clients and concurrent authorized calls. **Open.**

### M-02 — Medium residual: semantic fidelity is not provable from quoted JSON
- **Location:** `backend/app/services/intent_parser.py:165-219` (pre-fix range);
  new `frontend/app/page.tsx` intent-review dialog.
- **Sequence:** a model omits an unusual requirement, changes an attribute's value,
  or mislabels its key while quoting real text. Source presence/type checks cannot
  prove meaning; the buyer may overlook the difference during required review.
- **Impact/preconditions:** wrong purchase fit with human consent, not unauthorized
  financial authority. Clause checks can also reject otherwise valid mixed-role
  prose conservatively. No live parser accuracy or prompt-injection rate measured.
- **Fix/test:** explicit structured user corrections/confirmation and supported
  predicate semantics, plus adversarial evaluation and clarification on ambiguity.
  Keep human review mandatory and never let model confidence override hard denial.
  Test negation, grouped/mixed-role clauses, omitted constraints and paraphrases.
  **Open residual; High automatic-review bypass is contained.**

### M-03 — Medium: restart/lost-response recovery is not exposed as a casebook
- **Location:** `backend/app/services/approvals.py:63-66`;
  `backend/app/services/workspace.py:158-176`; `frontend/app/page.tsx:77-78,101-119,248-275`;
  `backend/app/services/checkout.py:153-167,339-357`.
- **Sequence:** reload/close the page after a capture request loses its response,
  or restart the backend. The browser loses its checkout ID and the backend loses
  canonical proposals/sessions/early audit. There is no authenticated checkout-list
  UI; proposal audit lookup fails after canonical loss. Known attempted checkout IDs
  still reconcile GET-only from the durable ledger, but the user cannot discover
  them through the casebook. Unknown/orphaned creates can remain permanently blocked.
- **Impact/preconditions:** stranded reservations, missing user-visible audit and
  operator recovery burden, not automatic double capture. Requires restart/lost
  browser state or inconclusive provider state.
- **Fix/test:** durable canonical authority and owner-filtered checkout recovery/list
  with GET-only reconciliation; an audited operator procedure for unknown creates
  and inconclusive captures. Test crash boundaries and fresh browser recovery; never
  reconstruct consent from storage or release uncertain holds by TTL. **Open.**

### M-04 — Medium: SQLite privacy/schema/provisioning assumptions are not enforced
- **Location:** `backend/app/services/checkout_store.py:21-59,104-124`;
  `backend/app/services/provisioning.py:69-99`; `docker-compose.yml:20-25`.
- **Sequence:** use a shared existing directory or Windows path: `chmod(0600)` is
  not a private Windows ACL, does not validate parent/backup permissions, and follows
  existing paths. `CREATE TABLE IF NOT EXISTS` has no schema-version/migration gate.
  Crash between separate account and policy creation commits leaves an account
  without policy; restart sees the account and skips policy seeding. Mapping changes
  overwrite trusted configuration, and `put_policy` permits different rules under
  the same version. No public API performs these writes.
- **Impact/preconditions:** ledger disclosure/tampering by another local principal,
  startup/schema incompatibility, or fail-closed unavailable workspace. Requires
  unsafe filesystem/deployment, changed schema/trusted configuration or crash.
  Windows ACL attack and power-loss durability were not simulated.
- **Fix/test:** protected OS-specific local directory/ACL and backups; schema version
  and reviewed transactional migrations; atomic account+policy bootstrap; immutable
  policy-version enforcement; deliberate mapping provisioning. Test interrupted seed,
  incompatible existing schema and filesystem permissions without touching real ledgers.
  WAL/FULL financial transactions already serialize holds/settlement. **Open.**

### M-05 — Medium: terminal local cancellation is not ongoing provider monitoring
- **Location:** `backend/app/services/checkout.py:342-343,362-363,423-432`.
- **Sequence:** locally cancel an order before dispatch. It becomes terminal FAILED;
  later an external merchant/app with provider authority captures that order. Both
  capture/reconcile return the local terminal record without another provider GET.
  Similarly, later refunds or reversals are outside the terminal lifecycle.
- **Impact/preconditions:** ledger/provider divergence and misleading "not completed"
  after external activity. Requires separate seller credentials/provider authority;
  an unsigned browser callback alone cannot do this. Existing preflight external
  capture discovery accounts for a completed order before local termination.
- **Fix/test:** supported provider void where applicable and authenticated provider
  monitoring/operator reconciliation of terminal records, separating local intent
  from observed financial truth. Test cancel, later exact external capture, then
  accounting without re-dispatch or invented refunds. **Open, documented limitation.**

### M-06 — Medium: development dependency denial-of-service advisory
- **Location:** `frontend/package-lock.json` minimatch under typescript-estree;
  `frontend/package.json:21-30` development dependency tree.
- **Sequence:** attacker-controlled glob/path input reaches affected tooling using
  minimatch, triggering globparts amplification (`GHSA-g3hv-75wg-m249`).
- **Impact/preconditions:** developer/CI denial of service, requiring untrusted
  tooling inputs. No production runtime exploit was established.
- **Evidence/fix/test:** current npm audit reports **seven moderate dependency nodes**
  for this dev-tool chain, not seven independent production vulnerabilities;
  `npm audit --omit=dev` reports zero. Upgrade the compatible dev dependency chain
  separately and rerun lockfile install/lint/build/audit. **Open; no broad audit fix run.**

### M-07 — Medium: browser test harness could target an existing ledger (hardened)
- **Location:** pre-fix `backend/tests/frontend_server.py:26,69-81`.
- **Sequence:** an operator points `RYUK_E2E_DB` at an existing database and runs the
  test server/reset route. Test hooks delete reservations/checkouts and reset settled
  spending. Hooks were excluded from production startup/image, but testing itself
  could corrupt real data through a trusted configuration mistake.
- **Impact/preconditions:** financial history loss when manually launching the test
  server against existing data. No such database was opened in this review.
- **Fix/test:** test server now always allocates fresh uniquely named temporary
  directories; new-case switches to another mock ledger and never deletes/resets
  records. The old database-file override is no longer used. Production-route and
  actual proxy tests reject fixture controls; Docker excludes backend tests.
  **Hardened as necessary test isolation for this review.**

## Remaining Low findings
- **L-01 — Low:** proxy allowlists paths but not per-path methods, and compares only
  origin host (`frontend/app/api/ryuk/[...path]/route.ts:4-24`). Unsupported methods
  reach upstream (which returns 405); wrong-scheme mutations are blocked by the
  backend's exact configured Origin. Set an exact origin/per-path method matrix and
  test unsupported methods, encoded traversal, redirects and scheme changes.
  **Defense-in-depth gap, not a verified authentication bypass.**
- **L-02 — Low:** no explicit CSP/frame-ancestors/referrer policy
  (`frontend/next.config.ts:3-7`, `frontend/app/layout.tsx`). Third-party SDK runs with
  page privileges; native dialogs do not prevent framing. Add a tested PayPal-compatible
  policy (including buyer popup/frame needs) and anti-framing headers. Test denied
  framing and the SDK flow without relaxing backend authority. **Open; no XSS found.**

## Verified security boundaries

Actual code reviewed: HTTP dependencies/DTOs, session hashing/lifecycle, canonical
approval ownership/CAS/expiry, proposal digest, pure policy/recomputed verifier,
workspace orchestration, SQLite claims/accounting, checkout coordinator, PayPal
OAuth/transport/mapping, Next proxy, SDK callbacks, client state/errors, Docker inputs
and test controls. Documentation was read first, not treated as implementation proof.

- Opaque cookie sessions are the implemented buyer auth, **not a Bearer-token API**.
  Unsigned Authorization/X-User-Id/JSON actor fields do not authenticate. PayPal OAuth
  uses backend-only Bearer tokens. Default unprovisioned financial routes fail closed.
- Ownership is checked in canonical approval access and durable checkout loading;
  pure policy also rejects mismatched user/budget/currency/history contexts. Demo auth
  intentionally has one buyer; production multi-account identity is not implemented.
- Browser amount/merchant/approval/success/order IDs cannot become checkout authority;
  input DTOs forbid extras. Hashes are regenerated from canonical intent/evidence and
  exact terms; approvals are owned, current, one-time, expiring and permanently invalidated.
- BEGIN IMMEDIATE plus unique proposal/payment/reservation claims serialize capture
  and available budget. Policy, digest, latest consent and merchant mapping reload at
  the final post-preflight claim. Holds and dispatch audit commit before POST; no
  canonical/database lock spans provider I/O. Settlement/release/state/audit rollback
  together, settle once and preserve uncertainty after crashes/transport failure.
- CAPTURE_PENDING/PENDING_PROVIDER recovery queries original immutable provider terms
  and never retries capture. Cancellation before the final claim prevents POST;
  cancellation after it cannot free an in-flight reservation. A commit is the
  dispatch authorization boundary; later revocation cannot undo dispatched payment.
- PayPal is fixed Sandbox HTTPS with redirects off/TLS on, stable operation-specific
  request IDs and no POST retry. Exact order ID, CAPTURE intent, single purchase unit,
  reference, seller, amount and currency are verified. Only one full, final COMPLETED
  capture within a COMPLETED order is success. Missing/partial/refunded/unknown
  evidence is pending; exact declines/failures and VOIDED-without-capture are failure.
  Provider live behavior, external order mutation and webhook authenticity are not
  established by mocks. No webhook endpoint accepts provider truth.
- SDK approval callbacks request backend processing only; no `actions.order.capture`
  or client paid flag. The application does not navigate provider-returned approval
  links; a fixed PayPal SDK script gets only public client ID, currency and backend
  order ID. React renders text rather than HTML. No app localStorage/sessionStorage
  token/authority storage or credential URL parameter was found.
- Environment credentials remain server-side; `.env` values were never opened. Backend
  Docker input allowlists exclude test hooks, fake parser fixtures and environment files;
  only deliberately labeled synthetic hotel catalog data is runtime input. No production
  fake provider fallback was found. Root `.env` existence is not provider readiness.

## Hypotheses / explicitly unverified
- Public ingress, trusted forwarded headers, TLS termination, host/DNS rebinding,
  actual Windows/container-volume ACLs, NFS/ephemeral deployment and backup access:
  deployment-sensitive risks, not observed remote exploits in this checkout.
- Live model semantic/prompt-injection rates, live SDK popup/account acceptance,
  exact real seller/capture behavior, power-loss storage durability, cross-process
  distributed canonical authority and long-lived operator recovery are unverified.
- No full historical secret audit or credential readiness check was attempted, because
  this task forbids inspecting secret values. No claims about absence of secrets in
  all Git history or infrastructure logs. Source/control-flow/bundle-marker checks are
  narrower evidence.

## Validation
Final results are recorded in STATUS.md and the completion summary below. All provider
traffic uses isolated fake parser/MockTransport/SDK fixtures; browser external traffic
is blocked. Disposable test ledgers are retained, not reset or deleted. No live model
or payment request, credential disclosure, financial reset, deployment or Step 13 work.

### Final verified results
- Pre-fix backend baseline: **983 passed**; six adversarial failures reproduced four
  High findings before fixes.
- Final backend: **1,004 passed**, no pytest warnings; Ruff and `pip check` pass.
- Frontend: ESLint, TypeScript and optimized production build pass. Intended standalone
  server used for final browser run: **36 Chromium assertions**, desktop/mobile,
  including origin/allowlist/method/redirect refusal, credential-safe errors, required
  intent review, mobile rejection, spoofed callback, cancellation and timeout recovery.
- Final browser JavaScript marker scan excludes backend credential names and synthetic
  secret markers; this is not an inspection of real secrets or a historical secret audit.
- npm audit: seven moderate dev dependency nodes; zero production dependency findings.
- Docker/Compose validation blocked: `docker` command is unavailable. Images were not
  rebuilt or deployed. Live parser/Sandbox/buyer acceptance and payment timing untested.

## Sandbox prerelease status addendum

The finding descriptions above retain their original evidence and historical status. Later hardening added bounded streaming bodies/auth allocations/model requests, method/redirect-aware proxy checks, frame/base/object/referrer/MIME headers and protected container data storage; these mitigate portions of M-01, M-04 and L-01/L-02, without closing all production requirements. M-07's fixture now requires explicit opt-in and creates fresh temporary ledgers. Read-only receipt export improves operator evidence but does not implement durable canonical history/discovery (M-03). Semantic residuals (M-02), terminal provider monitoring (M-05), migration/provisioning/ACL assumptions and development advisories remain. Full script CSP and public-scale resource protections remain pending. See [release limitations](release-notes.md) and [later hardening](security-hardening.md); historical finding/audit counts are not a new vulnerability scan.

## Durable authority follow-up

Runtime proposals/approvals and early audit now persist with the ledger; owner-scoped history permits rediscovery and audit inspection after reauthentication. This addresses the volatile-authority/discovery portion of M-03 for newly persisted records. Legacy checkouts remain discoverable without reconstructing lost consent. Uncertain/orphaned provider operations still need operator reconciliation; no terminal monitoring or refund/reversal flow is introduced. Migrations/atomic provisioning, public identity/availability and remaining residuals stay open. See [transaction and upgrade boundaries](durable-authority.md).

## Login-rate-limit follow-up

Addressed the shared proxy-IP login bucket: Compose ingress overwrites client headers, an authenticated private frontend/backend channel supplies normalized client IP, and the backend image disables Uvicorn forwarded-header trust. Direct requests ignore unverified assertions. Inactive limiter buckets are reclaimed. NAT/outer-proxy topology, private-network trust, process-local limits and distributed resource exhaustion remain limitations; see login-rate-limits.md.

## Script-CSP follow-up

The previously pending document script policy is now implemented with per-response nonces, dynamic/no-store SSR, production nonce/strict-dynamic script-src and blocked inline event attributes. PayPal loader propagates both nonce attributes. Existing frame/base/object controls remain. Browser tests exercise injection rejection and mocked SDK compatibility; third-party trust/delegation and unmeasured live SDK branches remain limits. See content-security-policy.md.
