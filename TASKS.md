# AgentPay Task Board

- [x] Temporary-clone approval layout and non-floating Sandbox notice; frontend checks and desktop/mobile fixture verification pass. No commit/push/deployment.

## P0 — Must ship

### Foundation
- [x] Repo initialized
- [x] Next.js frontend
- [x] FastAPI backend
- [x] .env.example
- [x] Docker Compose
- [x] health endpoints
- [x] lint/test commands

### Domain schemas
- [x] PurchaseIntent, Offer, CheckResult, VerificationResult, PolicyDecision, PurchaseProposal, ApprovalRequest, PaymentIntent
- [x] Strict integer minor units, explicit enums, and contract-validation tests

### Intent
- [x] PurchaseIntent schema
- [x] structured parsing
- [x] validation
- [x] 15 test prompts

### Catalog
- [x] hotels.json
- [x] 6+ synthetic offers
- [x] merchant IDs
- [x] evidence fields
- [x] search endpoint

### Verification
- [x] required attribute checks
- [x] preferred scoring
- [x] PASS/FAIL/UNKNOWN
- [x] verification snapshot (generated in memory with evidence and stable ID; persistence deferred)
- [x] evidence shown in UI (backend matrix, sources and snapshot)

### Policy
- [x] max budget rule
- [x] approval threshold
- [x] missing evidence rule
- [x] merchant review
- [x] duplicate/unknown-attempt policy checks against explicit backend history snapshots
- [x] read-only approval binding/expiry/rejection policy checks
- [x] duplicate protection (SQLite checkout uniqueness and atomic capture claim)
- [x] proposal digest

### Approval
- [x] request creation (internal in-memory service)
- [x] proposal binding (internal in-memory service)
- [x] expiry (internal in-memory service)
- [x] approve/reject service operations with one-time decisions
- [x] authenticated approve/reject endpoint (opt-in single-buyer demo session)
- [x] revalidation before checkout (backend gate; payment wiring deferred)
- [ ] durable approval storage and authenticated user integration

### Payment state machine
- [x] Exact nine-state vocabulary and centralized immutable event/transition graph
- [x] Illegal transitions, same-state moves, and terminal exits rejected
- [x] Approval returns to policy; pending-provider recovery requires reconciliation events
- [x] State-only updates preserve binding, identity, and idempotency; exhaustive tests
- [x] Durable conditional checkout state updates, coordinator integration, and checkout audit (SQLite reference)

### PayPal
- [ ] Sandbox accounts/app
- [x] server-side OAuth (Sandbox-only adapter; mocked HTTP)
- [x] create order (internal adapter; mocked HTTP)
- [ ] buyer approval
- [x] capture (internal adapter with provider approval preflight; mocked HTTP)
- [x] stable operation-specific PayPal-Request-Id (adapter; mocked HTTP)
- [x] durable operation-key/terms storage and atomic execution claim (SQLite)
- [x] get status and exact order/capture binding/state mapping (mocked HTTP)
- [ ] live Sandbox final-state acceptance
- [x] verified capture decline and local pre-dispatch cancel handling (mocked HTTP)
- [x] buyer UI cancel/decline/pending presentation (browser/provider mocks)
- [x] ambiguous timeout classification, no automatic capture retry, status reconciliation (adapter tests)
- [x] durable pending-provider GET-only recovery and held-budget accounting
- [ ] unknown-create/operator recovery procedure

### Checkout integration
- [x] Canonical proposal -> server-owned PayPal order -> provider-verified buyer approval -> capture (mocked HTTP)
- [x] Final reload/digest/current policy/approval/merchant mapping checks after provider preflight
- [x] Atomic reserve/dispatch claim, success settlement, verified-failure release, uncertain-hold retention
- [x] Identifier-only create/read/capture/reconcile/cancel HTTP contracts with forbidden authority fields
- [x] Default routes fail closed until trusted authentication/service provisioning
- [x] Duplicate/concurrent budget, expiry/tampering, transaction rollback and restart tests
- [x] Opt-in private demo password session and trusted runtime service provisioning
- [ ] Production multi-user identity and durable canonical authority
- [x] Buyer UI / actual PayPal JS v5 integration implemented and browser-mock tested
- [ ] Live Sandbox checkout acceptance

### Frontend — Stage 11
- [x] Sanitized setting-specific demo startup diagnostics and 21 configuration regression cases
- [x] Visible Ryuk branding and restrained dark editorial casebook design
- [x] Command input, backend intent, candidate records and evidence/preference detail
- [x] Backend policy verdict and exact-term approval/reject modal
- [x] Actual PayPal JS SDK/server order/capture integration; success only from backend
- [x] Backend result/reference/snapshot/available budget and audit timeline
- [x] Same-origin proxy, authenticated private session and explicit unavailable states
- [x] Production build, desktop/mobile browser integration and no secret-marker bundles
- [ ] Real configured model + real Sandbox buyer/capture acceptance (credentials absent here)
- [ ] Live happy path timed under three minutes
- [ ] Stage 11 acceptance complete; do not infer completion from mocked tests
- [x] Stage 12 actual-source security review and Critical/High remediation (four High fixes/containments; `docs/security-review.md`, D-033)
- [x] Step 12 validation: independently reproduced 983-test baseline; final 1,004 backend tests, Ruff/pip check, frontend lint/type/build and 36 standalone-production mocked browser assertions pass
- [ ] Step 12 remaining Medium/Low hardening: request/resource limits, semantic review residuals, durable recovery/discovery, SQLite ACL/migrations/atomic provisioning, terminal-provider monitoring, dev tooling and proxy/security headers
- [ ] Docker/Compose revalidation (Docker CLI unavailable in review environment; no deployment attempted)
- [x] Step 13 demo readiness (completed in final freeze below; historical live-timing gate remains separate)

### Audit
- [x] checkout execution/reservation/provider-observation events persisted in SQLite
- [x] checkout_audit table (checkout-only; broader domain audit remains pending)
- [ ] verification events
- [ ] policy events
- [ ] approval events
- [ ] provider events
- [x] timeline UI (backend canonical and checkout events; early records process-local)

### Demo
- [ ] ALLOW scenario
- [ ] REQUIRE_APPROVAL scenario
- [ ] DENY scenario
- [ ] amount tampering blocked
- [ ] duplicate payment blocked
- [ ] seed/reset command
- [ ] demo script

## P1 — Strong differentiators
- [ ] semantic evidence matcher
- [x] Step 12 adversarial extraction/role-shortening/omission tests with mandatory bound intent-review containment (not live model fidelity)
- [x] checkout duplicate/overspend concurrency tests (broader security review remains pending)
- [x] checkout merchant/provider mapping substitution tests (mocked HTTP)
- [ ] "Why this purchase?" summary
- [x] requirement matrix UI
- [ ] human review when evidence is insufficient

## P2 — Only if P0/P1 complete
- [ ] electronics verifier
- [ ] subscription verifier
- [ ] real external search API
- [ ] LangGraph checkpointing
- [ ] specialized subagents
- [ ] multi-rail adapter
- [ ] UPI Circle/P3P conceptual adapter
- [ ] team approvals

## Verified security / non-live readiness — 2026-11-11
- [x] Review latest origin/main implementation and preserve older local work separately
- [x] Authenticate model endpoint and enforce bounded model requests
- [x] Digest-bound mandatory review of original versus parsed intent for model purchases
- [x] Prevent validation/clarification credential reflection and unsafe HTTPS cookies
- [x] Streaming proxy body limits, bounded auth allocations and frame/security headers
- [x] Isolate test reset fixture to explicit fresh temporary ledgers
- [x] Retain backend-only Groq parsing with shared strict validation and mocked tests
- [x] Consistent private backup command and fresh-fixture recovery rehearsal
- [x] Update security report, operations runbook, demo script and D-033
- [x] 1,034 backend tests, frontend lint/type/build, 23 mocked browser assertions
- [x] Build both Docker images and verify isolated credential-disabled Compose health
- [ ] Real buyer-approved Sandbox acceptance and timed live demo freeze
- [ ] Production durable canonical authority/multi-user auth and operator orphan recovery
- [ ] Development dependency advisory resolution and full SDK-compatible script CSP

This current evidence supersedes earlier unchecked Step 12 instructions/counts. Step 13 preparation is done; live acceptance remains unverified. See STATUS.md for the authoritative current state.

## Merge repair — 2026-11-12
- [x] Resolve committed conflicts from cde0d08, preserving original workspace edits
- [x] Unify review flag/reason, validation handler and authenticated parser wrapper
- [x] Preserve both security test sets, improved review UI and source-role checks
- [x] Add conflict-marker regression for source/runbooks
- [x] 1,056 backend tests, Ruff, frontend lint/type/build and 44 mocked browser assertions
- [ ] Buyer-approved live Sandbox acceptance remains unverified

## Groq transport-schema compatibility — 2026-11-12
- [x] Reproduce real HTTP 400 integer/number anyOf overlap safely
- [x] Use equivalent non-overlapping Groq schema; retain strict backend/source checks
- [x] Add immutable/shared-schema regression and safe provider-status messages
- [x] Live gpt-oss-120b gold extraction accepted and validated (no payments)

Groq repair: 1,063 backend tests/Ruff/diff checks pass. User installation must pull and rebuild/recreate backend; no private key changes are required for the schema fix.

- [x] Reproduce and repair the unchanged UI example: numeric-only monetary grammar and role-bearing exact source evidence; live extraction validated, no payments.

## PayPal callback lifecycle — 2026-11-12
- [x] Reproduce premature Buttons.close during onApprove with failing browser regression
- [x] Retain SDK instance/nodes through terminal/pending callbacks; prevent further visible button action
- [x] Guard cancellation activity until its callback resolves
- [x] Frontend lint/type/build and 47 mocked production-browser assertions
- [ ] Verify user's current live payment state; never infer capture success from HTTP 200

## Acceptance receipts — 2026-11-12
- [x] Read-only CLI export of successful checkout/capture/audit/settlement evidence
- [x] Pending/missing ledger regression checks, no financial writes/provider calls
- [x] Independently export the separate USD100 test receipt from this workspace
- [ ] Export the user's website payment receipt locally and retain UI confirmation screenshot

## Required scenario verification — 2026-11-12
- [x] Approval required, including below-threshold model-intent review and separate buyer consent
- [x] Budget denial and independent requested/policy/available ceilings
- [x] Mandatory attribute denial under budget; API refuses review/checkout with zero provider/ledger activity
- [x] Browser authority fields and changed canonical/provider terms blocked
- [x] Repeated/concurrent handlers cannot create duplicate order/capture/settlement or overspend holds
- [x] Focused 32-test run and documented reproducible matrix (docs/required-scenarios.md)

These are isolated automated scenarios; no new live payment was made and no existing ledger was reset. Full live UI timing/demo freeze remains distinct.

## Final revision checks — 2026-11-11 UTC
- [x] Re-run backend suite (1,070), Ruff and dependency consistency at source revision 31367ae
- [x] Re-run frontend lint/typecheck/production build and 47 mocked browser assertions against freshly built standalone output
- [ ] Confirm user's deployed source/artifact revision and run deployed smoke checks; local build results do not establish deployment acceptance

See STATUS.md for the validation scope. This rerun made no live payment or existing ledger changes.

## Step 13 — walkthrough and Sandbox source release
- [x] Prepare three-minute run of show, including honest prior-evidence mode for spent budgets
- [x] Finalize tagged startup/update/stop, Groq and Sandbox buyer/seller instructions
- [x] Record user-reported 0b24df8 healthy local containers and passing website receipt, without publishing private evidence
- [x] Document remaining security/production limitations and source-tag scope
- [x] Prepare annotated v0.1.0-sandbox-demo tag; publish only after final source checks pass
- [ ] Measure an actual under-three-minute buyer-approved live run; the prepared schedule is not timing evidence
- [ ] Independent inspection of user's private website receipt/provider match (not required to publish this explicitly scoped prerelease)

The latest release summary in STATUS.md supersedes older “not started”/pending preparation entries. Production work remains open; no ledger reset or new charge is part of this release task.

## Requested six-scenario regression and demo documentation
- [x] Run complete backend suite: 1,070 passed
- [x] Confirm eligible, approval required, budget denied, mandatory attribute denied, duplicate prevented and amount tampering prevented in test results
- [x] Run Ruff/dependency consistency and frontend lint/typecheck/production build
- [x] Update existing docs/demo-script.md with the six-case rehearsal and test references; align acceptance matrix
- [x] Keep application implementation unchanged; use isolated mocks and preserve financial records/release tag
- [x] Complete fresh standalone browser suite: 47 assertions passed; stop isolated fixture servers

## Production-readiness stage 1 — durable authority/recovery
- [x] Persist canonical proposals, current/historical approval decisions, expiry/revocation and early audit
- [x] Reload authority under the same SQLite transaction as financial claims; no provider I/O while locked
- [x] Add owner-scoped bounded/paginated saved history and frontend inspection/reconciliation without capture
- [x] Retain legacy checkout discovery/audit while failing closed for lost pre-upgrade consent
- [x] Add restart, revocation, concurrency, rollback, legacy and history regressions
- [ ] Subsequent stages: versioned migrations/provisioning, multi-user identity, resource quotas, provider lifecycle and remaining security/operations work
- [x] Stage 1 validation: 1,082 backend tests, Ruff/pip consistency, frontend lint/typecheck/build and 51 mocked browser assertions

## Step 13 final freeze — current authoritative checklist
- [x] Run complete backend suite and six required scenario regressions at durable runtime source 8497325
- [x] Run frontend lint/typecheck/production build and isolated browser suite
- [x] Finalize docs/demo-script.md and startup/recovery instructions without new features
- [x] Document residual security/production limits and distinguish private receipts from independent evidence
- [x] Prepare tested v0.1.1-sandbox-demo source freeze, preserving the old tag
- [ ] Actual buyer-approved live walkthrough timed under three minutes (external acceptance evidence, not certified by automated Step 13 checks)

Step 13 in CODEX_PROMPTS.md is tests, scenarios and demo documentation with no new features. Remaining production-readiness stages are separate and not marked complete.
- [x] Final packaging: both images rebuilt, isolated credential-disabled Compose services healthy, backend/frontend smoke checks and fail-closed session response passed
- [x] Record mock suite duration 36.67 seconds without claiming live-buyer timing

## Proxy-aware login throttling
- [x] Isolate client buckets using authenticated, normalized ingress-derived IPs
- [x] Overwrite browser identity headers at ingress; do not publish frontend directly
- [x] Disable Uvicorn forwarded-header trust and keep direct-peer fallback distinct
- [x] Reclaim inactive bounded-client entries and add spoof/isolation regressions
- [x] Document new private proxy setting and trust/NAT/distributed limitations
- [x] Validate 1,090 backend tests, 51 browser assertions, lint/type/build/Ruff and real Docker ingress client isolation/spoof resistance

## Definitive decline and operator recovery
- [x] Preserve narrow authenticated capture-decline evidence bound to original request/order
- [x] Recheck provider binding/capture state before atomic release; prioritize observed capture truth
- [x] Add read-only hold listing and audited GET-only operator reconciliation
- [x] Keep unknown/historical unproven outcomes held; no force-release, new order or capture retry
- [x] Add decline, restart/repeat, unknown-error, pending/success-priority and read-only regressions
- [x] Full backend validation: 1,102 tests, Ruff/dependency consistency and diff checks passed

## Document script CSP hardening
- [x] Per-response nonce, dynamic SSR, caller-header overwrite and no-store document handling
- [x] Enforce production script-src without unsafe-inline/eval and block inline handler attributes
- [x] Pass nonce/data-csp-nonce to PayPal loader and retain scoped provider resources
- [x] Add browser nonce/cache/loader/injection-blocking regressions
- [ ] Real Sandbox SDK/approval recheck after frontend deployment (mock compatibility is not live certification)
- [x] Frontend validation: lint/typecheck/production build and 62 mocked browser assertions; diff checks pass

## Presentation polish pass — 2026-11-12
- [x] Verify clean release baseline and read required instructions/current contracts
- [x] Task 1: persistent Sandbox/synthetic/no-real-money notes on pages and dialogs
- [x] Task 2: explain all 16 backend reason codes beside unchanged codes; generic fallback
- [x] Task 3: existing settled/held/available values with zero/exhausted budget presentation
- [x] Task 4: clearer waiting/slow/empty/error and pending-capture guidance without request/decision changes
- [ ] Task 5: source-quote associations absent from response; stopped without backend/API changes
- [ ] Task 6: deferred after task 5 stop boundary; README unchanged
- [ ] Task 7: deferred after task 5 stop boundary; no new architecture diagram

Constraints and validation details: docs/presentation-polish.md. All work remains local; no dependency additions or financial/ledger/provider/auth modifications.
- [x] Validation: 1,102 backend tests (no skips), 22 presentation tests (no skips), lint/typecheck/build and 81 isolated Chromium assertions; fixture servers stopped

## Authorized source-quote links — task 5 continuation
- [x] Retain already-validated requirement quotes with role/name and Unicode code-point spans
- [x] Validate exact source spans and complete/unique associations at the domain boundary
- [x] Preserve legacy quote-less serialization; bind new provenance with existing intent snapshots/digests
- [x] Show original/parsed requirements side by side with source highlights and keyboard links
- [x] Preserve previous uncommitted presentation work and expose honest legacy missing-source text
- [ ] Later requested tasks: README, architecture diagram, packaging; do not start in this turn
- [ ] Separate future production migrations/auth/operations work
- [x] Source-link validation: 1,114 backend tests, 25 helper tests, 98 browser assertions, lint/typecheck/build, Ruff/pip/diff checks; isolated fixtures only

## README polish — requested next task
- [x] One-line pitch and honest real-screenshot placeholder without invented imagery
- [x] Three-command quick start aligned with startup.md and current Compose services
- [x] Preserve private configuration/existing ledgers and all prior safety claims
- [x] Note local work versus published release scope; check links/whitespace
- [ ] Next task: architecture diagram (not started here)
- [ ] Later packaging and separately authorized production migrations/operations work

README/STATUS/TASKS only changed in this turn; runtime validation remains the prior 1,114 backend / 25 helper / 98 browser passing result, not a new run. No commit, tag, push, deployment or live provider calls.

## Architecture diagram — requested next task
- [x] Document the implemented model-derived flow as Mermaid with source references
- [x] Mark untrusted LLM output, deterministic backend trust boundary and spending invariant
- [x] Show separate exact application consent/PayPal buyer authorization and durable recovery limits
- [x] Link diagram from README and verify local links/source structure/whitespace
- [ ] Next requested stage: final checks/packaging (not started here)
- [ ] Separate production migrations and remaining hardening stages

Documentation only; runtime files and earlier local changes preserved. No commit, tag, push, deployment or live financial activity.

## Combined checks and review package — 2026-11-12
- [x] Rerun full backend suite: 1,114 pass, zero failures/errors/skips
- [x] Rerun 25 frontend tests, lint/typecheck/production build and 98 isolated browser assertions
- [x] Verify protected financial/auth/provider/SQL/CSP files remain unchanged and docs links resolve
- [x] Package tracked/new-file patch, manifest, summary and fixture screenshots outside the repository
- [x] Check patch applicability using a temporary index; leave the real worktree/index uncommitted
- [ ] User review before any commit/push; no tag or deployment authorized in this turn

The bundle contains no credentials, ledger files or real payment evidence. Provider/SDK/model behavior is mocked; live timing/acceptance is not claimed. No subsequent production stage started.

## User-approved publication — 2026-11-12
- [x] Explicit approval to publish the reviewed presentation/source-provenance/docs batch
- [x] Verify all 24 reviewed files match before documentation publication-status edits
- [x] Preserve release tags, existing financial records and unrelated work
- [ ] Separate production migrations/auth/operations stages remain unstarted
