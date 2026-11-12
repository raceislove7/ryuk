# Ryuk Status

Approval-dialog presentation polish in the temporary submission clone: stacked original/parsed review, compact responsive requirement cards and wrapped exact-term details. Sandbox notices are in normal flow, not floating over content. Frontend lint/typecheck/build and isolated desktop/mobile dialog overflow, notice scrolling and close-control checks pass. No approval/payment logic changed, no approval decision/checkout performed; uncommitted and not deployed.

## Current: user-approved presentation/provenance publication — 2026-11-12

User reviewed the prepared batch and explicitly requested publication. The 24-file review package matched the worktree before this documentation status update. Runtime changes retain the recorded 1,114 backend / 25 frontend / 98 browser passing evidence; no code changed after review. Publish through the verified mittalsukhansh connection, preserving the existing release tags and financial records. No deployment or subsequent production stage is included. The local/unpublished notes below describe the pre-approval review stage.


## Current: local review package — 2026-11-12

Reran the combined presentation/source-provenance/README/architecture work against baseline 1c49165. **1,114 backend tests passed (zero failures/errors/skips), 25 frontend tests passed (zero skips), and 98 isolated Chromium browser assertions passed**. Frontend lint/typecheck/production build, Ruff, dependency consistency, documentation links and whitespace checks pass. Financial-control/auth/PayPal/SQL/CSP implementation files remain unchanged. Only fresh temporary fixture ledgers and mocked model/SDK/provider responses were used; fixture processes stopped after testing.

Prepared an external review bundle with complete tracked/new-file patch, manifest, summary and fixture screenshots. Verified the patch against the base with a separate temporary Git index; the real index/working tree remain uncommitted. No tag, push or deployment. Live provider acceptance, measured live timing, full screen-reader testing and external Mermaid rendering are not claimed. Remaining production work is separate. Earlier local changes are preserved.


## Current: architecture diagram documentation — 2026-11-12

Added docs/architecture-demo.md with the implemented model-derived request/LLM/validator/verifier/policy/exact-approval/PayPal-Sandbox/ledger flow, a marked backend trust boundary and the invariant “The LLM proposes; only the deterministic backend authorizes spending.” Includes separate buyer authorization, pre-capture reload/atomic claims, durable records and GET-only uncertainty recovery, with source links and honest synthetic/private-demo limits. Linked from README. No runtime code or architectural behavior changed; DECISIONS.md needs no new entry. Existing local work preserved; packaging/migrations remain separate.

Documentation links, diagram source structure and Git whitespace checked. No fresh runtime test run for this documentation-only task; prior 1,114 backend / 25 helper / 98 browser results remain the latest runtime evidence. Mermaid rendering in external Markdown clients is not independently certified. No tag, push, deployment, live provider calls or ledger access.


## Current: README presentation polish — 2026-11-12

Updated only the README opening with a one-line pitch, explicit real-screenshot placeholder (no fabricated screenshot/broken image link), three-command current-checkout quick start matching docs/startup.md, and honest Sandbox/synthetic/single-buyer scope. Existing implementation and safety/evidence statements are preserved below it. Configuration remains a private manual step before startup; no commands were deployed/executed against a demo installation. Existing local presentation and provenance changes are preserved. Architecture diagram, packaging and production migrations have not started. Documentation/link/whitespace checks pass; no runtime changes or additional runtime test run in this documentation-only turn.


## Current: authorized requirement source links — 2026-11-12

Parser-validated requirement quotes now survive into PurchaseIntent/API responses as optional requirement_sources associations (role/name/exact quote/Unicode span). Domain validation checks association completeness/uniqueness and exact spans. Existing records without sources serialize as before, preserving old snapshot/digest inputs; new source metadata is included by the existing full-intent bindings. UI shows original request beside parsed mandatory/preferred requirements with highlighted source quotes and keyboard links. No policy/approval/checkout/PayPal/auth/ledger logic or SQL schema change. See docs/intent-provenance.md and D-045.

Validation: **1,114 backend tests passed** (12 new provenance regressions), **25 frontend helper tests passed**, and **98 isolated Chromium assertions passed**, including source links/focus, legacy fallback and existing CSP/financial-flow mocks. Frontend lint/typecheck/production build, Ruff, dependency consistency and diff checks pass. Screenshots reviewed; fixture processes stopped. This is the explicitly authorized continuation of presentation task 5. Earlier local tasks 1–4 remain preserved. README, architecture diagram, packaging and production migrations have not started; older task-5 blocked notes below are historical. No live model/payment calls, existing ledger/volume mutation, tag, push or deployment.


## Current: presentation polish only — 2026-11-12

Clean baseline 1c49165 in the release worktree; older checkout preserved. Added persistent Sandbox scope notes, display-only explanations for all 16 backend reason codes plus unknown fallback, settled/held/available bars from the existing workspace values, clearer empty/error states and a 15-second presentation-only waiting notice. No backend/API/schema, financial/session/PayPal controls, ledger, provider loader or CSP configuration changed. No dependencies added. See docs/presentation-polish.md.

Stopped at task 5: original request source quotes are validated internally but not exposed as requirement provenance in PurchaseIntent/the current response. No quotes were inferred or fabricated. Task 5 needs an explicitly authorized backend/API change; tasks 6/7 were deferred per the user's ordered stop rule. Existing intent review and README safety claims remain unchanged. DECISIONS.md is unchanged because no meaningful architecture/authority decision changed.

Validation: **1,102 backend tests passed**, no skips (count unchanged); **22 frontend presentation tests passed**, no skips; frontend lint/typecheck/production build passed; **81 isolated Chromium browser assertions passed**, including CSP nonce/injection regressions, desktop/mobile, zero/exhausted bars, empty shortlist and slow/error guidance with no automatic retry. Screenshots inspected. Protected backend/API/PayPal/auth/CSP files have no diff; Git whitespace checks pass. Fixture processes stopped afterward. No credential values inspected, live provider calls, existing financial record/volume changes, tag, commit, push or deployment. Live SDK/buyer flow, assistive-technology testing and a measured three-minute run are not certified by these isolated checks.


## Current: nonce-based document script CSP

Added per-response cryptographic nonces in the Next proxy, dynamic SSR nonce propagation and private/no-store HTML. Production script-src uses nonce/strict-dynamic with provider compatibility fallbacks, no unsafe-inline/eval, and script-src-attr none. PayPal receives both nonce and data-csp-nonce; missing nonce fails loading closed. Explicit resource/frame/connect restrictions retain the existing frame/base/object protections. See docs/content-security-policy.md and D-044. Validation: frontend lint/typecheck/production build pass and **62 mocked browser assertions pass**, including actual CSP violation events for blocked scripts/handlers, unique/caller-independent nonces and SDK attributes. Backend unchanged; its last full 1,102-test result is historical, not a new rerun in this frontend-only change. Backend financial rules and deployment credentials are unchanged; no live payment or deployment performed. Mocked SDK tests do not certify all real PayPal SDK branches; real Sandbox validation remains an external gate.


## Current: explicit decline evidence and operator hold recovery

Retain validated INSTRUMENT_DECLINED capture rejection evidence with its original dispatch key; GET and verify the exact bound order before resolving the hold. Completed/pending capture evidence takes precedence. Added local read-only hold discovery and audited explicitly applied GET-only operator reconciliation; no force-release/capture-retry path. Legacy unknown outcomes without saved evidence remain held pending provider truth. See docs/operator-recovery.md and D-043. Validation: **1,102 backend tests passed** (12 new recovery regressions), Ruff and dependency consistency passed, Git whitespace checks passed. Frontend is unchanged; no browser/image rebuild claim for this backend-only change. No live provider call, installation deployment or existing financial reset performed.


## Current: proxy-aware login throttling

Implemented authenticated ingress-derived IP keys for login; browser forwarding headers cannot choose their bucket. Compose publishes Nginx instead of the frontend, Next/backend share a private proxy token, and Uvicorn ignores proxy headers for direct peer identity. Inactive login buckets are reclaimed before the bounded client-cap check. Requires RYUK_PROXY_SHARED_SECRET in the private .env and recreation of backend/frontend/ingress; see docs/login-rate-limits.md and D-042. Validation: **1,090 backend tests** and **51 mocked browser assertions** passed; frontend lint/typecheck/build and Ruff passed. Isolated Docker ingress testing confirmed forged headers cannot rotate the first socket client’s exhausted allowance while an independent second socket can sign in. Backend/frontend/ingress health checks pass; the ingress loopback probe ignores outbound proxy settings. No installation deployment, live provider call or financial record changes were performed. Public multi-user/distributed availability controls remain separate.


## Current: Step 13 demo-readiness freeze

Step 13 from CODEX_PROMPTS.md is complete in scope: all tests, six required scenarios and finalized demo instructions; no runtime features added in this freeze. Source baseline 8497325 includes the separately completed durable-authority stage. Prepare v0.1.1-sandbox-demo after final checks; retain v0.1.0-sandbox-demo unchanged. Final results: **1,082 backend tests**, all six scenarios, **51 mocked browser assertions** (36.67 seconds for the automated suite), Ruff/pip consistency and frontend lint/typecheck/production build pass. Both Docker images built in the isolated credential-disabled ryuk-step13-final project, both containers healthy, backend health OK, frontend HTTP 200, and session configuration/authentication false as expected. Compose config and Git whitespace checks pass. Rehearsal containers were stopped with volumes retained. Detailed results below are authoritative over older pending/not-started entries.

This is not production completion. Actual buyer-approved under-three-minute live timing remains unmeasured; user-reported private website receipt/container evidence is from 0b24df8. No new payment, secret disclosure or existing financial ledger reset is part of this freeze.


## Latest: durable authority and recovery implementation

Production-readiness stage 1: runtime canonical proposals/approvals and early audit now persist in the existing SQLite ledger; final consent and reservation/dispatch claims share a transaction. Added owner-scoped paginated saved history and inspection/GET-only provider reconciliation in the frontend. Sessions still require reauthentication after restart. Legacy checkout references are discoverable without inventing lost pre-upgrade consent. See docs/durable-authority.md and D-040. Historical process-local authority limitations below describe earlier revisions.

Validation: **1,082 backend tests passed** (12 new durability/history regressions), Ruff/dependency consistency pass, frontend lint/typecheck/production build pass, and **51 mocked browser assertions passed**, including reload/history/audit recovery with zero create/capture POSTs. No live provider call, existing ledger reset or deployment was performed. The previously tagged Sandbox release remains unchanged.

This does not implement production multi-user auth, PostgreSQL/versioned migrations, quotas, terminal provider monitoring/refund/reversal execution or production deployment. Existing accounts/holds/settlements remain untouched; all execution tests use fresh fixtures and mocked provider transport.


## Latest milestone — private Sandbox release preparation

Prepared `v0.1.0-sandbox-demo`: finalized startup/update/stop instructions, three-minute run of show, release evidence and remaining production/security limitations. Application code is unchanged from the 1,070-test/47-browser-assertion baseline; final source-tag checks run before tagging. See docs/release-notes.md. Earlier pending statements below are historical and superseded where evidence is recorded here.

User-reported local evidence: checkout 0b24df8, both rebuilt Compose containers healthy, and existing website payment export checks_passed=true. Private receipt/UI/provider details were not independently inspected by this agent. Retain receipt and success screenshot privately. The separate earlier USD100 evidence is not substituted for that website payment.

Step 13 items 4/5 are prepared for release. **An actual under-three-minute live rehearsal remains unmeasured**; this schedule/source tag does not certify it or production readiness. No additional payment, financial reset, deployment or image rebuild was performed for documentation/release preparation. Existing spending must be preserved; the default presentation reuses labeled prior payment evidence.


## Groq compatibility repair — 2026-11-12
Reproduced a real provider HTTP 400: Groq rejects the overlapping integer/number branches in the extracted attribute anyOf schema. Compile only the Groq transport schema by removing the redundant integer branch (number already includes integers), retaining the shared strict Pydantic/source/domain validation and mandatory original/parsed intent review. No JSON-mode downgrade, coercion or provider fallback.

Live gpt-oss-120b extraction on the committed synthetic gold request now passes strict backend validation with the expected finite budget. A different synthetic phrasing requested clarification rather than bypassing validation; this is not proof of semantic completeness or live payment acceptance. No payment call was made. Provider HTTP failures now produce code-owned authentication/access/model/rate/request messages without provider bodies or secret reflection. Current regression results are recorded below.


## Current verification — merge repair, 2026-11-12
Repaired latest GitHub commit cde0d08 in an isolated worktree. Original local edits, private configuration and financial records were preserved.

- Removed committed merge markers from seven files; consolidated duplicated review flags, policy enum members and validation handlers.
- Canonical review field: intent_review_required. Preserved original/parsed intent digest binding, source-clause role checks, HTTP authentication/origin/rate limits, and both security test sets.
- Preserved the readable original/parsed review UI and combined browser coverage. Earlier hardening report retained separately in docs/security-hardening.md.
- **1,056 backend tests pass**, Ruff passes; frontend lint/typecheck/production build pass; **44 mocked production-browser assertions pass** using the installed Chromium (CHROMIUM_PATH=/usr/bin/chromium).
- New source/runbook regression rejects committed conflict markers.
- No live model/provider/payment calls, financial reset/deletion or deployment. Docker not rebuilt for this repair. Live buyer-approved Sandbox acceptance remains pending.

## Earlier milestone notes
The following sections retain historical evidence/counts; the verification above is current.


Last verified: 2026-11-11, latest GitHub baseline 674bdf0 plus this security/demo-preparation change. Changes were prepared in an isolated worktree; older workspace edits were preserved.

## Current milestone
Step 12 — Current-source security review completed with four confirmed High findings fixed/contained and documented regression evidence. Remaining Medium/Low risks are open in `docs/security-review.md`. **Step 11 live acceptance remains incomplete**; no live model/Sandbox transaction or timing was attempted. Step 13 has not started.

## Implemented
- Existing casebook UI, synthetic catalog, deterministic evidence/policy/approval, PayPal SDK/backend adapter and atomic persistent SQLite checkout coordinator retained.
- Mandatory application review of original versus parsed intent for every model-derived workspace purchase, bound by proposal digest v2. This prevents automatic bypass, not semantic incompleteness or inattentive consent.
- Authentication on the formerly public parser endpoint; private workspace parser already has actor isolation. Bounded model allowance separate from payment status/reconciliation.
- Static validation/clarification responses without private input/context reflection; HTTPS cannot disable secure session cookies.
- Bounded auth allocations, bounded streaming proxy bodies, frame/MIME/referrer headers and isolated temporary-only test reset fixture.
- Backend-only Groq provider selection/config forwarding, strict schema and shared source/domain validation, preserving earlier local Groq work on the newer remote architecture. No provider fallback.
- Operator-only consistent SQLite backup to new mode-0600 output with overwrite/symlink refusal and integrity checks; no ledger resets.
- Security report with exploit sequences/recommendations: docs/security-review.md. Backup/recovery/mock-runbook: docs/operations.md. Updated demo script and pending live acceptance record: docs/demo-script.md. Decision D-033.

## Verification
- Backend: **1,034 tests passed**, no warnings; Ruff and pinned dependency consistency pass.
- Frontend: ESLint, TypeScript and optimized production build pass.
- Browser: **23 assertions passed** through actual production UI/proxy/API/SQLite with isolated model/SDK/provider mocks. Covers original/parsed review, rejection, denial, delayed capture confirmation, reconciliation, no premature success, origin/path/body/auth controls, private cookies, security headers, desktop/mobile layout and runtime errors.
- npm production audit: **zero** findings. Full audit: **eight moderate development-tool** advisories, no High/Critical.
- Docker: CLI/daemon available here; both images built with CA trust preserved. Separately named credential-disabled Compose project uses isolated ports/volume; backend/frontend healthy, backend health OK and frontend HTTP 200. Compose config and diff whitespace checks pass.
- No live model/provider/payment calls, private secret-value inspection, or existing financial record reset/deletion in this stage. Mock reset actions are confined to newly created temporary fixture ledgers.
- The externally supplied 1,004-test/36-assertion review summary was not present in origin/main; it was not independently verifiable and is superseded by the evidence above.


## Completed
- [x] Next.js/TypeScript/Tailwind and FastAPI/Compose foundation, strict integer-money domain contracts, eight labeled synthetic hotel offers and trusted search.
- [x] Deterministic evidence-backed required/preferred verification and snapshots, structured OpenAI parser interface/fake/15 test prompts and pure financial policy.
- [x] Canonical digest v2 and process-local approval ownership/expiry/permanent invalidation/replay checks; exact nine-state payment graph. Backend-owned intent-review flag and intent-bearing snapshot bind all model-derived workspace proposals to explicit application consent.
- [x] Backend Sandbox OAuth/create/status/capture adapter, immutable provider binding, stable request IDs and safe ambiguous outcomes.
- [x] Durable SQLite checkout/payment/key/terms/state/ledger/hold/checkout-audit records; atomic final policy/approval/digest/merchant/reservation claim, exactly-once settlement/release and GET-only uncertainty recovery.
- [x] Visible Ryuk branding, original monochrome casebook with restrained red, serif/monospace typography, subtle grain, three-record primary shortlist and optional expansion. No franchise artwork or generic AI gradients/glassmorphism.
- [x] Working command entry and backend-parsed intent display, backend candidate/verdict/evidence/preference matrix, exact-term approve/reject dialog, snapshot and backend timeline.
- [x] Real SDK integration code: server-owned order ID -> PayPal buyer authorization -> backend capture. Result waits for backend SUCCEEDED; callback alone never displays paid. Pending state offers reconciliation, not a capture retry.
- [x] Thin workspace/proposal/approval/audit APIs reuse existing services; query/identifier/decision bodies reject browser authority fields.
- [x] Explicitly enabled single-buyer demo password verification, opaque hashed session tokens, HttpOnly/SameSite cookie, origin checks, rate limit/logout; default missing configuration stays blocked. Direct parser HTTP now authenticates before provider initialization; HTTPS cannot disable Secure cookies.
- [x] Same-origin Next proxy with allowlisted paths, credential isolation, no cache/redirect forwarding and safe errors. Only PayPal's public client ID reaches the SDK.
- [x] Trusted runtime account/policy/payee provisioning and protected persistent Compose ledger volume. Startup preserves existing funds/holds and never resets spending.
- [x] Independently reran pre-fix baseline: **983 passed**. Six new failing pre-fix assertions reproduced four High findings. Final backend suite **1,004 passed** (21 additional regression cases), no pytest warnings; Ruff and `pip check` pass.
- [x] Frontend ESLint, TypeScript and optimized production build pass. Chromium against the intended standalone production server passes **36 assertions** over actual Next proxy/FastAPI/services/SQLite with mocked SDK/provider, desktop/mobile and mobile intent-review dialog, no page errors or horizontal overflow. No live timing claim.
- [x] Browser bundles checked for backend credential names/synthetic-secret markers; image inputs reviewed for test/environment exclusion. Secret values were not inspected; no full historical credential-audit claim. Docker/Compose validation could not be rerun because the Docker CLI is unavailable here.
- [x] Step 12 fixes: authenticated billable parser; enclosing-clause role checks plus mandatory exact intent review for every model-derived workspace proposal; input-free validation errors; enforced secure HTTPS cookies. Detailed exploit sequences/preconditions/fixes/tests and remaining risks: `docs/security-review.md`, D-033.
- [x] Browser test harness now allocates new isolated mock ledgers per case, never deletes reservations or resets existing financial records. Production fixture-control routes and proxy forwarding are rejected; redirect regression proves no upstream redirect is followed.

- [x] Local startup troubleshooting fix: setting-specific sanitized diagnostics, validated HTTPS/loopback origins, preflight budget/merchant checks and SQLite error classification; 21 regression cases pass. The user’s exact local invalid setting remains unconfirmed until they run the updated image.

## In Progress
- [ ] Step 11 live acceptance remains unverified. This review deliberately made no real model/payment calls and did not inspect private provider configuration. UI/integration mock evidence is not live acceptance.

## Remaining
### P0
- [ ] Make actual provider configuration available to the runtime and run the real structured parser/Sandbox checkout through the UI. No production fake fallback exists.
- [ ] Verify live SDK popup, separate buyer authorization, backend provider-confirmed capture/reference, ledger settlement and audit under three minutes.
- [ ] Complete Step 11 live acceptance before calling the demo ready. Step 12 was explicitly requested and reviewed without performing that live acceptance.
- [ ] Durable canonical proposal/approval/evidence and early audit storage; these remain process-local. Production multi-user identity and multi-worker authority deployment remain unimplemented.
- [ ] Operator recovery for unknown/orphaned creates and permanently inconclusive captures; preserve uncertain holds.
- [ ] Validate the proposed demo script on a live Sandbox run. Checkout/audit browser flow is mock-tested, not live accepted.

### P1
- [ ] Residual semantic omissions/changed meaning need buyer scrutiny and separate evaluation; automatic review bypass is contained, not semantic completeness proven.
- [ ] Bound request buffering, parser quotas/concurrency, session/canonical retention and proxy-aware login limiting (M-01).
- [ ] Enforce schema migrations, OS-specific ledger/backup ACLs, atomic provisioning and immutable policy versions (M-04).
- [ ] Address terminal-provider monitoring, dev-tool advisory chain and proxy/header defense-in-depth gaps (M-05/M-06/L-01/L-02).
- [ ] Production PostgreSQL-backed authority/ledger deployment and migration; SQLite remains a single-host reference.
- [ ] Extend visual/accessibility/browser/device coverage after live acceptance; desktop and phone are verified, not all device/provider combinations.

### P2
- [ ] Other purchase verticals, real external search, multi-rail/team approvals and conceptual UPI/P3P.
- [ ] LangGraph/specialized agents only after the core demo works.

## Blockers
- Live acceptance was outside this review's permitted actions. A root `.env` exists in this local checkout but its values were never opened; existence does not establish provider readiness. Keep it private, not in chat/Git upload.
- Actual model/Sandbox account, seller verification and buyer popup/capture behavior remain unverified by mocks. No provider credential readiness assertion is made.
- Docker CLI is unavailable; Compose/container validation and image rebuild were not performed. No deployment changes were applied.
- A private demo also needs opt-in password/origin/cookie configuration. Production multi-user authentication and durable canonical authority are still separate limitations.

## Risks
- Demo auth and canonical approvals/early audit are process-local/single-buyer. Restart invalidates sessions/consent and blocks new capture; durable attempted captures still reconcile using original terms.
- SQLite must use a protected persistent local directory/volume, not ephemeral storage or NFS. Pending holds cannot be released just because time passed or the browser closed.
- Candidate verdicts are backend snapshots; selection and capture recheck current rules/budget. One USD 1,500 ledger cannot fund both USD 1,180 and USD 1,390 successful demo purchases.
- Local cancellation does not void a PayPal order; refunds/external merchant actions and long-lived provider uncertainty need operator support.
- Hotel data is synthetic and checkout targets a configured demo payee, not a real hotel booking. Preference percentages cannot override mandatory checks or financial rules.
- Live model fidelity, SDK/account behavior and buyer timing are not established by mocks.
- Current npm audit reports seven moderate **development dependency nodes** in one minimatch/TypeScript-ESLint advisory chain; `npm audit --omit=dev` reports zero. Dev-tool upgrade remains separate work; no broad audit fix or lockfile rewrite was performed.
- Source-role checks and required human review cannot prove complete model fidelity. Resource limits, reload discovery/operator recovery, SQLite/ACL/migration/provisioning and external-terminal-provider monitoring remain open; see M-01 through M-06 and L-01/L-02.

## Next 3 actions
1. Review the remaining Medium/Low findings and separately authorize prioritized hardening; protect the existing ledger and private settings.
2. When explicitly permitted, complete Step 11 real model/Sandbox acceptance and timing without substituting mocked evidence.
3. Stop after Step 12. Step 13 requires a separate instruction.

## Demo readiness
- Intent parsing: UI and protected backend parser orchestration implemented; fake/SDK tests pass. Live model response/fidelity unverified.
- Offer search: Backend candidates appear in the shortlist; six USD records from eight labeled fixtures, top three initially visible. No live hotel availability or booking.
- Verification: Real backend evidence/status/preference counts and snapshot displayed in matrix; no invented evidence/PASS.
- Policy: Backend deterministic verdict/reasons displayed. UI does not calculate eligibility. Current rules rerun before capture with an atomic hold.
- Approval: Every model-derived proposal requires original/parsed intent review; exact terms/expiry/reasons use authenticated backend consent. Process-local authority remains a deployment limitation.
- PayPal: Actual SDK integration and server-order/capture/status code complete; mock browser flow passes. **Real Sandbox buyer/capture acceptance remains unverified and Step 11 remains incomplete.**
- Audit: UI uses backend canonical/approval events and durable checkout events/timestamps. Early events remain in memory; broader durable audit deployment is pending.
- Security review: Step 12 actual-source review and isolated adversarial regressions complete; four High findings fixed/contained, Medium/Low residuals documented. Live demo and production deployment are not certified.

## Test status
- Unit: Backend `pytest -q`: **1,004 passed**, no pytest warnings; independently verified pre-fix **983 passed**; Ruff passes; `pip check` reports no broken requirements.
- Integration: Real-adapter/SQLite checkout tests plus authenticated session/proxy/workspace paths, exact backend evidence/verdicts, consent, forbidden fields, origin/owner checks, cancellation races, duplicate/overspend, rollback and restart/lost-response GET-only recovery pass. Bundle marker check passes. Compose validation blocked by missing CLI.
- E2E: Standalone production Next -> same-origin proxy -> actual FastAPI/services/SQLite -> mocked SDK/HTTP provider: **36 Chromium assertions** pass at 1440px/390px. Required intent-review/rejection, secret-safe errors, origin/allowlist/method/redirect checks, spoofed callback, cancellation, no false success, timeout reconciliation and mobile dialog pass. Test external browser traffic is blocked. Not real Sandbox acceptance.
- Security: Confirmed High reproductions, bound review, authenticated direct parser, input-safe errors, cookie hardening and existing financial tampering/race/recovery tests pass. No production deployment, power-loss durability or live provider acceptance claimed.

Step 12 changes application review policy for model-derived proposals and advances the canonical digest format; active financial caps, payment graph, atomic claims/accounting and GET-only uncertainty recovery are unchanged. Provider credentials remain backend-only. Only isolated mock backend and local standalone production frontend were booted for validation. No secret values read, live calls/captures, existing financial resets/deletes, image rebuild, deployment or Step 13 work.

Groq repair validation: 1,063 backend tests pass (including schema-equivalence and sanitized provider-status regressions), Ruff and diff checks pass. Workspace tests explicitly isolate provider selection from inherited live Groq configuration. Live gold extraction passed through strict validation on gpt-oss-120b; no payment operation performed. Frontend unchanged by this backend-only repair.

## UI example monetary evidence repair — 2026-11-12
Reproduced the exact screenshot prompt live: the model placed currency text in amount_text, then another response omitted the monetary role cue from its quote. The prompt now explicitly separates numeric tokens from currency. Groq transport constrains numeric amount grammar and, where exact role-bearing/currency-bearing source spans are available, narrows budget/threshold quote/amount enums to those spans. No coercion, default budget, financial policy change or automatic fallback. Strict backend source/money validation and human intent review remain in force. The screenshot's unchanged text now passed live gpt-oss-120b validation. No payment call performed.

UI example repair validation: 1,066 backend tests, Ruff and diff checks pass. Exact screenshot prompt live-validates with 150000/130000 minor-unit money and mandatory amenities preserved. This is a tested extraction case, not a general semantic guarantee; no financial execution occurred.

## PayPal SDK callback lifecycle repair — 2026-11-12
Confirmed that a terminal/pending capture response caused the parent to unmount PayPalCheckout and invoke Buttons.close while the SDK onApprove promise was still running. A realistic mock lifecycle regression failed before the fix (one premature close). Keep SDK nodes mounted for the selected purchase, hide further button action on non-awaiting states, and let the SDK finish its own callback/window cleanup. Local cancellation now holds the UI busy until its callback completes too.

Frontend lint/typecheck/production build and 47 production-browser assertions pass, including success/pending/cancellation lifecycle guards. Backend financial rules, keys, claims/reservations and no-retry semantics are unchanged; no backend tests were rerun for this frontend-only repair. No live provider/payment call or user payment-status claim in this stage. HTTP 200 alone does not prove SUCCEEDED; inspect the existing payment's state before any new purchase. Update/recreate frontend only to avoid resetting in-memory backend authority.

## Read-only acceptance evidence export — 2026-11-12
Added app.export_acceptance CLI for the operator to export recorded capture/order/payment references, backend state, minimal audit and exact-once settlement checks from the local SQLite ledger. Read-only/query-only snapshot; no provider calls or resets. Credentials, actor identity, request text, idempotency keys and arbitrary audit details are omitted. Default receipt filenames are Git-ignored.

The separately authorized USD100 Sandbox test in this workspace has exported evidence: recorded SUCCEEDED, capture reference, exactly one dispatch/settlement, matching settled reservation and 15 audit events. This does not certify the user's separate website payment or UI timing; that receipt must be exported from their local Docker ledger. No new payment was attempted in this task.

Evidence exporter validation: 1,069 backend tests passed; Ruff and diff checks passed. Frontend unchanged; no live provider operation performed. Actual receipts remain private outside Git.

## Required scenarios verified — 2026-11-12
Approval-required, budget-denied, mandatory-requirement-denied, tampering-blocked and duplicate-prevented checks pass in a focused 32-test run. New API regression proves an under-budget USD980 no-gym offer cannot create an approval/order, with zero provider calls or funds settled/reserved. Existing approval/buyer gates, canonical/browser tampering and duplicate/concurrency tests were rerun. Evidence and commands: docs/required-scenarios.md. No financial implementation change, live payment, private configuration change or existing ledger reset.

Required-scenario final validation: 1,070 full backend tests passed; focused acceptance run 32 passed; Ruff and diff checks pass. Frontend/financial implementation unchanged in this verification task.

## Final revision revalidation — 2026-11-11 UTC

Validated clean source revision `31367ae338faf494d6bbbcc5a0d6265c3585c6ad`, matching origin/main when checked. This is source/build validation in the managed workspace, not evidence that the user's deployed installation runs this revision.

- Backend: 1,070 tests passed; Ruff and pip dependency consistency passed.
- Frontend: lint, TypeScript and fresh production build passed.
- Browser: 47 assertions passed against the newly built standalone server and isolated FastAPI/SQLite fixtures, with mocked SDK/model/provider, desktop/mobile.
- Git whitespace checks passed. No application implementation changed; no live provider/payment calls or existing financial ledger mutations occurred.
- Deployment identity, running artifact/configuration and deployed smoke checks remain unverified. No Docker image rebuild or deployment was performed in this rerun. User-local receipt export and timed live acceptance remain separate pending evidence.

## Six-scenario full regression rerun

Requested scope: run all tests, ensure eligible/approval-required/budget-denied/mandatory-attribute-denied/duplicate-prevented/amount-tampering-prevented scenarios, and maintain docs/demo-script.md. No features or application code changed; source baseline 9a3897f, with documentation-only updates.

Backend suite: 1,070 passed. JUnit results explicitly confirm all six scenario regressions, including canonical amount mutation during provider preflight. Ruff and dependency consistency pass. Frontend lint, TypeScript and fresh standalone production build pass. The existing demo script now includes the six-case rehearsal table and named automated evidence; the acceptance matrix includes trusted eligible checkout and clarifies that model-derived requests still require review. Documentation local links and Git whitespace checks pass.

Tests use isolated fixture ledgers and mocked model/SDK/provider; no live payment, existing ledger reset or deployment. Timed live acceptance and security/production residuals remain unchanged. Release tag is preserved.

Browser rerun: **47 assertions passed** against the freshly built standalone server and fresh FastAPI/SQLite fixture, with mocked SDK/provider and desktop/mobile flows. Fixture servers stopped afterward. All requested automated checks passed. The authenticated GitHub connection was subsequently verified as mittalsukhansh for publication of these documentation changes. The existing Sandbox release tag remains unchanged.
