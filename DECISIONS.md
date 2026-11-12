# AgentPay Decisions

Append-only Architecture / Product Decision Log. Record meaningful technical, product, security, architecture, scope, and integration decisions; omit trivial formatting and typo changes. Start at D-001 and append new sequential entries. Never rewrite historical decision bodies. When a decision changes, append a replacement, mark the previous entry Superseded, and link the entries in their status/supersession metadata.

These entries capture existing planning decisions, not completed implementation. Dates record when decisions were captured in this log; original decision dates are not established. Alternatives describe the choices implied by the planning constraints, not a claim that an earlier evaluation occurred.

## D-001 — LLM proposals have no payment authority
Date: 2026-11-11
Status: Accepted

### Context
Language models interpret user requests and untrusted listing content.

### Decision
The LLM may parse, rank, explain, and propose. Only deterministic backend services authorize financial actions; the payment adapter performs PayPal calls. The LLM cannot capture, change limits or approved terms, or declare success.

### Alternatives considered
- Let the LLM execute payment tools directly
- Let model confidence override backend decisions

### Why
This preserves the explicit reasoning/authority boundary and limits prompt-injection impact.

### Consequences
Financial behavior can be checked independently of model output; backend validation and orchestration are required.

### Constraints / assumptions
All model outputs, listing text, external tool output, and browser inputs remain untrusted.

### Related files
- `AGENTS.md`
- `ARCHITECTURE.md`
- `PLAN.md`
- `README_START_HERE.md`

### Supersedes / superseded by
None.

## D-002 — Deterministic financial policy
Date: 2026-11-11
Status: Accepted

### Context
An attractive offer can still violate spending or merchant constraints.

### Decision
Use a pure deterministic backend policy service returning DENY, REQUIRE_APPROVAL, or ALLOW_ELIGIBLE_FOR_CHECKOUT with reason codes. Enforce budget, currency, mandatory checks, approval threshold, merchant review, duplicate protection, expiry, and proposal revalidation.

### Alternatives considered
- LLM-selected financial decisions
- Client-side policy enforcement

### Why
Explicit rules make financial authorization reproducible and testable.

### Consequences
Hard failures cannot be overridden by prompting; policy versions and canonical backend inputs must be managed.

### Constraints / assumptions
ALLOW_ELIGIBLE_FOR_CHECKOUT does not replace required application approval or PayPal buyer authorization.

### Related files
- `PLAN.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`
- `AGENTS.md`

### Supersedes / superseded by
None.

## D-003 — Verify purchase intent before payment
Date: 2026-11-11
Status: Accepted

### Context
Spending controls alone cannot ensure that a purchase matches the request.

### Decision
Compare the selected offer with typed intent before payment, separating mandatory requirements from preferences and retaining verification evidence and a snapshot. Revalidate before capture.

### Alternatives considered
- Check only price and budget
- Review semantic correctness after payment

### Why
Intent-aware pre-payment verification is the flagship product requirement.

### Consequences
Incorrect purchases can be blocked before funds move; verification and evidence add work to checkout.

### Constraints / assumptions
Preference scores never replace mandatory checks or financial policy.

### Related files
- `PLAN.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-004 — Three-state evidence-backed verification
Date: 2026-11-11
Status: Accepted

### Context
Offer evidence may be false, incomplete, or ambiguous.

### Decision
Return only PASS, FAIL, or UNKNOWN. Mandatory false means FAIL; missing mandatory evidence means UNKNOWN; all mandatory requirements verified means PASS. Every semantic PASS needs supporting evidence. Mandatory UNKNOWN requires review; mandatory FAIL is denied.

### Alternatives considered
- Binary pass/fail with guessed missing facts
- Use a confidence score to override deterministic failures

### Why
UNKNOWN represents insufficient evidence without fabricating certainty.

### Consequences
Incomplete offers trigger review and may slow checkout; decisions remain explainable.

### Constraints / assumptions
LLM interpretation is limited to evidence-backed semantic checks; subjective or ambiguous cases require review.

### Related files
- `AGENTS.md`
- `PLAN.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-005 — PayPal Sandbox is the MVP payment rail
Date: 2026-11-11
Status: Accepted

### Context
The demo needs a supported real integration with bounded scope.

### Decision
Use PayPal Sandbox Orders API v2, the PayPal JavaScript SDK for buyer approval, and server-side create/capture/status calls through a PayPal adapter. Use an AgentPay-controlled or compatible Sandbox demo merchant.

### Alternatives considered
- Production payment processing for the MVP
- Claim direct payment to arbitrary merchants

### Why
The planning scope explicitly selects Sandbox and excludes arbitrary-merchant payment claims.

### Consequences
The demo can exercise provider checkout; it does not establish production readiness or universal merchant support.

### Constraints / assumptions
Compatible Sandbox buyer/merchant accounts and app credentials must be configured; credentials stay server-side.

### Related files
- `PLAN.md`
- `AGENTS.md`
- `CODEX_PROMPTS.md`
- `env.example`

### Supersedes / superseded by
None.

## D-006 — Buyer approval and expiring application approval
Date: 2026-11-11
Status: Accepted

### Context
Policy eligibility and user consent are separate requirements.

### Decision
Always preserve PayPal buyer authorization. Collect application approval when policy requires it; bind it to user, proposal, merchant, amount, currency, policy version, and verification snapshot. Expire approvals and invalidate them when bound fields change.

### Alternatives considered
- Skip PayPal buyer approval for policy-eligible purchases
- Reuse blanket or expired application approvals

### Why
Consent must apply to the exact purchase and satisfy provider requirements.

### Consequences
Users can review escalated purchases; changed terms require renewed approval and additional UI/state handling.

### Constraints / assumptions
Application approval cannot override hard policy denial or substitute for PayPal buyer approval.

### Related files
- `PLAN.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`
- `AGENTS.md`

### Supersedes / superseded by
None.

## D-007 — Bind approvals to a canonical proposal digest
Date: 2026-11-11
Status: Accepted

### Context
Approved terms can be tampered with or changed before checkout.

### Decision
Hash a canonical payload containing user_id, offer_id, merchant_id, amount_minor, currency, policy_version, and verification_snapshot_id. Bind approval to that digest; regenerate and compare before checkout/capture.

### Alternatives considered
- Bind approval only to an offer ID
- Trust browser-submitted merchant and amount

### Why
A digest ties authorization to exact backend-verified terms.

### Consequences
Changes invalidate approval; canonicalization and immutable snapshot references must be implemented consistently.

### Constraints / assumptions
The backend reloads canonical data and reruns policy; hashing alone does not establish authorization.

### Related files
- `ARCHITECTURE.md`
- `PLAN.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-008 — Represent money in integer minor units
Date: 2026-11-11
Status: Accepted

### Context
Intent, offers, policy, and payment records need consistent monetary values.

### Decision
Store money in integer minor units and carry currency explicitly across domain schemas and payment binding.

### Alternatives considered
- Binary floating-point money
- Use display-formatted monetary strings as internal values

### Why
The coding rules and schema task explicitly require integer minor units.

### Consequences
Internal arithmetic is exact; display and provider-boundary conversion must respect currency units.

### Constraints / assumptions
Currency mismatch is denied; no currency-conversion behavior is specified by the plan.

### Related files
- `AGENTS.md`
- `PLAN.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-009 — Idempotent payment execution
Date: 2026-11-11
Status: Accepted

### Context
Duplicate requests or repeated payment attempts can charge the same proposal twice.

### Decision
Give every payment attempt a unique internal ID, bind it to one canonical proposal, use a stable idempotency key, and deny duplicate payment attempts for the same approved proposal.

### Alternatives considered
- Create a fresh idempotency key on every retry
- Rely on the UI to prevent duplicate clicks

### Why
Duplicate prevention must hold at the backend and provider boundary.

### Consequences
Retries can be correlated safely; durable attempt records and duplicate enforcement are necessary.

### Constraints / assumptions
Idempotency does not resolve ambiguous provider outcomes by itself; see D-010.

### Related files
- `AGENTS.md`
- `PLAN.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-010 — Reconcile ambiguous provider outcomes before retry
Date: 2026-11-11
Status: Accepted

### Context
A capture timeout does not prove that payment failed.

### Decision
Move ambiguous outcomes to PENDING_PROVIDER, query provider state before any retry, and reconcile the internal result. Display paid only after provider-confirmed success.

### Alternatives considered
- Blindly retry capture after timeout
- Treat timeout as confirmed failure or success

### Why
Provider reconciliation avoids duplicate capture and false payment status.

### Consequences
An uncertain result can remain pending; status queries and reconciliation audit events are required.

### Constraints / assumptions
Provider status and events must be verified server-side; never invent provider semantics.

### Related files
- `ARCHITECTURE.md`
- `AGENTS.md`
- `PLAN.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-011 — Modular backend instead of microservices
Date: 2026-11-11
Status: Accepted

### Context
The hackathon MVP needs clear boundaries without unnecessary deployment complexity.

### Decision
Organize one FastAPI backend into focused parser, catalog, verifier, policy, approval, payment, audit, and provider-adapter modules rather than introducing microservices.

### Alternatives considered
- Independent microservices for each component
- One undifferentiated service with mixed responsibilities

### Why
The planned single backend layout and instruction to avoid unnecessary microservices favor a small, testable modular monolith.

### Consequences
Local integration and debugging are simpler; internal module boundaries still require discipline.

### Constraints / assumptions
This records the existing planned structure, not an implemented deployment.

### Related files
- `PLAN.md`
- `AGENTS.md`
- `ARCHITECTURE.md`

### Supersedes / superseded by
None.

## D-012 — Use trusted synthetic fixture data for the MVP
Date: 2026-11-11
Status: Accepted

### Context
Reproducible search and evidence are needed without requiring a live search integration.

### Decision
Build the initial catalog from trusted, clearly labeled synthetic fixtures with at least six hotel offers, merchant IDs, structured attributes, evidence, and source fields. Real search APIs remain optional later work.

### Alternatives considered
- Require live external search before the demo
- Present synthetic listings as real merchant availability

### Why
The fixture catalog makes the core safety workflow reproducible and is explicitly accepted by the scope.

### Consequences
Less external dependency and more predictable tests; listings do not prove real-world booking availability.

### Constraints / assumptions
Fixture status must be visible; fixture catalog data is still subject to verification and policy.

### Related files
- `PLAN.md`
- `TASKS.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-013 — Hotels are the initial demo vertical
Date: 2026-11-11
Status: Accepted

### Context
The demo needs a concrete purchase with mandatory and preferred attributes.

### Decision
Start with the hotel scenario: budget and approval threshold, required gym/mountain view/free cancellation, and preferred private pool. Demonstrate eligible, approval-required, and denied outcomes.

### Alternatives considered
- Build electronics and subscriptions simultaneously
- Use a generic purchase demo without concrete evidence

### Why
The hotel example and initial fixture task provide a defined end-to-end demonstration.

### Consequences
Hotel checks and UX can be focused; other category verifiers remain P2.

### Constraints / assumptions
Hotel offers are synthetic demo data; checkout uses the compatible Sandbox merchant, not arbitrary hotel booking systems.

### Related files
- `PLAN.md`
- `TASKS.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-014 — Defer multi-agent orchestration
Date: 2026-11-11
Status: Accepted

### Context
Multi-agent coordination adds complexity before the core checkout flow is established.

### Decision
Begin with one orchestrated workflow. Defer specialized subagents and LangGraph checkpointing to P2 after core P0/P1 work; any future agents still produce proposals only.

### Alternatives considered
- Multi-agent orchestration as a prerequisite
- Delegate financial authority to specialized agents

### Why
One workflow is easier to test, debug, secure, and demo.

### Consequences
The critical path stays smaller; advanced orchestration capabilities wait.

### Constraints / assumptions
Financial authority remains outside every agent even if orchestration is expanded.

### Related files
- `ARCHITECTURE.md`
- `TASKS.md`
- `PLAN.md`

### Supersedes / superseded by
None.

## D-015 — Atomically reserve available budget
Date: 2026-11-11
Status: Accepted

### Context
Concurrent requests can each pass a budget check and jointly overspend.

### Decision
Compute available budget as limit minus settled amounts minus active reservations. Reserve atomically before irreversible payment action, after current proposal, policy, and approval revalidation.

### Alternatives considered
- Check balance without reservation
- Reserve only after capture

### Why
Atomic reservations address concurrent overspend across payment attempts.

### Consequences
Concurrent requests cannot safely reuse the same available funds; reservation lifecycle management is required.

### Constraints / assumptions
The implementation must provide transactional atomicity; detailed reservation lifecycle rules remain to be implemented.

### Related files
- `ARCHITECTURE.md`
- `PLAN.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-016 — Centralized payment states and isolated provider adapter
Date: 2026-11-11
Status: Accepted

### Context
Checkout spans verification, approvals, provider interaction, and uncertain results.

### Decision
Use explicit enum-based payment states, centralized transitions, and illegal-transition rejection. Isolate PayPal URLs, OAuth, operations, and provider mapping in the PayPal adapter.

### Alternatives considered
- Ad hoc payment status updates across routes
- Mix provider calls into the LLM or frontend

### Why
This makes payment progression and provider trust boundaries explicit.

### Consequences
States and transitions can be tested; a transition table must still be implemented.

### Constraints / assumptions
ARCHITECTURE.md includes VERIFYING while CODEX_PROMPTS.md task 8 omits it. Resolve that detail during the state-machine stage rather than treating either list as implemented.

### Related files
- `AGENTS.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-017 — Typed validated interfaces and the MVP stack
Date: 2026-11-11
Status: Accepted

### Context
Untrusted natural-language and browser data must enter a maintainable application.

### Decision
Use Next.js, TypeScript, and Tailwind for the frontend; Python, FastAPI, and Pydantic for the backend. Require structured LLM output and schema validation. Prefer PostgreSQL for persistence, pytest for backend tests, and frontend tests where useful.

### Alternatives considered
- Accept unvalidated free-form model output
- Introduce an unrelated application stack

### Why
The required stack and typed boundary rules are explicit project instructions.

### Consequences
Contracts can be checked consistently; scaffold, migrations, and test infrastructure are still needed.

### Constraints / assumptions
PostgreSQL is a preference, not a documented absolute requirement. Playwright is conditional on time. Never infer unlimited budget from missing intent.

### Related files
- `AGENTS.md`
- `PLAN.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
None.

## D-018 — Audit verified decisions and provider outcomes
Date: 2026-11-11
Status: Accepted

### Context
The demo must explain why a purchase was allowed, reviewed, blocked, or paid.

### Decision
Record verification, policy, approval, budget reservation, provider actions, and reconciliation as audit events; retain verification snapshots and expose a timeline/result view. Payment success requires server-side provider confirmation.

### Alternatives considered
- Show only a final paid flag
- Trust client-reported success or unverified provider events

### Why
The project requires a verifiable audit trail for the full decision path.

### Consequences
Decisions become inspectable; persistent audit records and UI work are required.

### Constraints / assumptions
No secrets in source or raw credential-bearing exception dumps. Audit records must respect the same credential boundary.

### Related files
- `PLAN.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
- `TASKS.md`

### Supersedes / superseded by
None.

## D-019 — Stage-scoped delivery and a safety-focused demo freeze
Date: 2026-11-11
Status: Accepted

### Context
The MVP must remain reviewable and prioritize correctness over feature breadth.

### Decision
Execute only the requested stage, run relevant checks, maintain status and meaningful decision records, report blockers, recommend the next stage, and stop. Prioritize correctness, payment safety, reproducibility, and clear UX. Freeze features for demo readiness and exercise safe and blocked checkout scenarios.

### Alternatives considered
- Build the entire project in one task
- Automatically proceed to the next stage or add features during demo freeze

### Why
The staged prompts, execution instructions, and MVP priorities require bounded, verifiable increments.

### Consequences
Progress is easier to assess; later stages wait for explicit instructions. Documentation must track implemented evidence rather than planned checklists.

### Constraints / assumptions
Security-sensitive code needs tests. Demo readiness requires real Sandbox checkout, one approval escalation, blocked unsafe behavior, and an audit explanation.

### Related files
- `AGENTS.md`
- `PLAN.md`
- `CODEX_PROMPTS.md`
- `README_START_HERE.md`
- `TASKS.md`

### Supersedes / superseded by
None.

## D-020 — Credential-free foundation with two Compose services
Date: 2026-11-11
Status: Accepted

### Context
The scaffold stage must boot the required frontend and backend without implementing AI or payment behavior. Persistence has no consumers or domain models yet.

### Decision
Provide a Next.js App Router preview and a FastAPI API in two Compose services. Use a standalone production frontend image, non-root runtime users, loopback host ports, and HTTP health checks. `/health` reports process liveness only. Defer database provisioning, domain schemas, AI, and payment integrations to their requested stages. Make `.env.example` the canonical configuration template with empty credential fields; retain the original `env.example` for reference. Keep credentials out of frontend configuration and build contexts. Support the managed environment's public proxy CA through an optional build-time secret mount.

### Alternatives considered
- Require database and provider credentials to boot the scaffold.
- Add unused database services and AI/payment endpoints during foundation work.
- Copy the session proxy CA into image layers or disable TLS verification.

### Why
A credential-free, bounded scaffold can be validated independently. Two services implement the current stage while preserving the planned modular backend and future PostgreSQL preference. Build-time CA mounts preserve TLS verification without persisting session-specific trust files.

### Consequences
Local and Compose startup are available without third-party accounts. Health checks establish liveness, not full product readiness. Persistence and integrations remain incomplete. The frontend Dockerfile installs dependencies and builds in one layer to reduce temporary disk consumption on the managed environment's VFS Docker storage; source changes therefore rerun installation rather than reusing a separate dependency layer.

### Constraints / assumptions
This is a development foundation, not a production deployment or working checkout. No live provider readiness or payment safety is asserted. Only current non-secret configuration is passed to Compose services; future integrations must explicitly wire their backend configuration. Proxy CA overrides are environment-specific and kept outside the repository.

### Related files
- `frontend/Dockerfile`
- `frontend/next.config.ts`
- `backend/app/main.py`
- `backend/Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `.gitignore`
- `README.md`
- `PLAN.md`

### Supersedes / superseded by
None. Implements the foundation within D-005, D-011, and D-017; the PostgreSQL preference remains unchanged.

## D-021 — Explicit validated domain records without execution authority
Date: 2026-11-11
Status: Superseded

### Context
The domain-schema stage needs interoperable typed records before catalog, verification, policy, approvals, and checkout services are implemented. Loose coercion, ambiguous units, and conflicting snapshots would weaken later trust boundaries.

### Decision
Implement the eight requested Pydantic contracts in `app.schemas`, forbidding unexpected fields. Require nonnegative actual integers for monetary minor units, explicit budget/approval thresholds, positive integer quantities, and timezone-aware timestamps. Currency validation checks uppercase three-letter shape only. Required and preferred attribute maps cannot overlap; attributes support JSON values and offer evidence is keyed by attribute. Use explicit state/outcome/reason enums. Preference scores use 0–100 percentages and optional semantic confidence uses 0–1; both are finite and cannot override required checks or missing evidence.

Require semantic PASS evidence and verify aggregate consistency against supplied mandatory checks, with FAIL taking precedence over UNKNOWN. Bind approval/payment records explicitly to proposal, user, offer, merchant, amount, currency, policy version, verification snapshot, and a lowercase SHA-256-shaped digest. Draft proposals may omit evaluated results and digest; supplied snapshots must match their offer/policy references. Preserve denied offers as representable records. Approval times are validated structurally, including historical decisions on expired records; current authorization/expiry and transitions remain service responsibilities. Payment records default to CREATED and application approval PENDING and require an explicit idempotency key. Include VERIFYING from the architecture's fuller state vocabulary; add CURRENCY_MISMATCH to name the plan's existing currency rule.

### Alternatives considered
- Coerce monetary floats, strings, or booleans, or infer a missing budget as unlimited.
- Accept arbitrary result/status strings and silently ignore unexpected fields.
- Implement policy evaluation, digest generation, payment transitions, or provider calls inside schema validation.
- Reject over-budget proposals at ingestion, preventing the planned denial/explanation workflow.

### Why
Explicit shape and cross-record consistency make future interfaces testable without granting untrusted inputs financial authority or prematurely building later stages. Schema-level state vocabulary is distinct from a payment transition service.

### Consequences
Invalid/coercible money, inconsistent snapshots, unsupported state strings, and semantic PASS without evidence are rejected early. Clients must supply explicit units, thresholds, references, and timestamps. Tests cover JSON round trips and adversarial boundary inputs. Currency allowlisting, evidence authenticity, digest calculation, current approval checks, canonical lookup, duplicate prevention, transition legality, and provider verification remain unimplemented; a schema-valid record is not authorization.

### Constraints / assumptions
Zero is explicit zero, not unlimited; currency conversion and storage/provider integer limits remain later integration concerns. Missing mandatory evidence means UNKNOWN unless a mandatory failure exists. Digest format selects SHA-256 for future generation but does not implement hashing or prove binding. Records can describe historical states and must be revalidated by services; Pydantic models and nested collections are not treated as immutable security records.

### Related files
- `backend/app/schemas/domain.py`
- `backend/app/schemas/__init__.py`
- `backend/tests/test_domain_schemas.py`
- `docs/domain-schemas.md`
- `PLAN.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
Superseded by D-027 for payment-state vocabulary only (VERIFYING removal). All other domain-contract decisions remain in effect.

## D-022 — Read-only labeled fixtures and explicit catalog retrieval
Date: 2026-11-11
Status: Accepted

### Context
The hotel catalog stage needs reproducible offers and evidence without live hotel APIs. Retrieval must preserve unknown and unsafe candidates for later verification and policy instead of presenting search as purchase authorization.

### Decision
Add eight synthetic offers in `fixtures/hotels.json`, labeled at catalog, offer title, source, and response levels. Prices are integer minor-unit totals for one room and the stated nights, including fictional taxes/fees. Include the planned three demo prices, a false mandatory amenity, missing cancellation evidence, and different currency/country/stay-length cases. Merchant identifiers are fictional and are not provider merchant mappings.

Load and validate the entire read-only catalog at application startup. Missing/invalid fixtures, duplicate offer IDs, absent synthetic labels, or schema-invalid offers prevent startup. Return deep copies from search and canonical ID lookup. Expose POST /v1/offers/search with explicit AND-combined country, nights, currency, price, boolean-attribute, and lexical title/location filters, stable offer-ID ordering, and bounded pagination. A price ceiling requires currency; no currency conversion, semantic matching, policy evaluation, or automatic filtering from PurchaseIntent occurs. Missing boolean attributes match neither true nor false. Preserve evidence gaps unchanged.

Use the repository root as the backend Docker build context, allowlist runtime inputs in root .dockerignore, and retain the /app/backend plus /app/fixtures layout so fixture lookup works independent of working directory, locally and in containers.

### Alternatives considered
- Require external search APIs, real inventory, or real merchant accounts before the demo.
- Return unlabeled offers or silently treat missing evidence as confirmed attributes.
- Apply implicit budget/mandatory filtering or price comparisons across currencies.
- Return mutable internal offer objects, silently overwrite duplicate IDs, or serve a partial invalid catalog.
- Duplicate fixtures under backend solely for Docker packaging.

### Why
A labeled, fail-closed fixture catalog makes search reproducible and testable while preserving the later verification/policy stages. Deep copies protect canonical in-memory records from callers, and root-context packaging keeps a single fixture source in local and container execution.

### Consequences
Search runs without credentials, network calls, or database setup and is documented/tested at service and HTTP boundaries. Malformed fixtures prevent API startup; editing them requires restarting the app. Lexical filters do not interpret free-form purchase intent, and results do not certify requirements, budget, merchant eligibility, or payment permission. Backend image builds must use the repository root context; the allowlist excludes environment files, tests, development dependencies, and unrelated content. No frontend search UI is added yet.

### Constraints / assumptions
Fixtures are not real hotels, dated availability, booking contracts, or supported payment destinations. Boolean filters use actual boolean types; an integer 1 cannot satisfy true. Currency codes retain domain-schema validation, with matching offers restricted to the supplied currency before a price filter. A search price ceiling is a retrieval constraint, never a replacement for later financial policy. Actual verification, digest/approval binding, reservations, and provider integration remain subsequent stages.

### Related files
- `fixtures/hotels.json`
- `backend/app/services/catalog.py`
- `backend/app/schemas/catalog.py`
- `backend/app/api/offers.py`
- `backend/app/main.py`
- `backend/tests/test_catalog.py`
- `backend/Dockerfile`
- `.dockerignore`
- `docker-compose.yml`
- `docs/catalog.md`

### Supersedes / superseded by
None. Implements D-012 and D-013. Refines the backend packaging in D-020 while retaining the same two-service architecture and no database dependency.

## D-023 — Evidence-backed typed equality and independent preference scoring
Date: 2026-11-11
Status: Accepted

### Context
The deterministic verification stage must distinguish known requirement failures from insufficient evidence and keep optional preferences from overriding mandatory constraints. The existing records need explainable preferred checks and stable verification references without implementing policy, approvals, or payments.

### Decision
Implement verify_offer for explicit required/preferred attribute maps using exact same-type primitive equality. Supported values are booleans, integers, finite floats, and nonblank strings. Unsupported predicates, absent/null/blank actual values, and incompatible types produce UNKNOWN; no coercion, fuzzy matching, ranges, or prose interpretation occurs. A known same-type mismatch is FAIL even if evidence is absent. A matching value without per-attribute evidence is UNKNOWN, and an evidence-backed match is PASS. An explicit false requirement can match an evidenced false value.

Aggregate required status with FAIL before UNKNOWN; no required attributes yields UNKNOWN rather than vacuous PASS. Add backward-compatible preferred_checks to VerificationResult, with unique names disjoint from required checks. Compute equal-weight preference percentage from evidenced PASS checks divided by all preferences; no preferences yields zero. Preferences never alter mandatory status. Missing-evidence names refer only to required checks with absent/empty evidence. No model confidence is generated.

Revalidate input records and produce ordered checks without input mutation. Derive an in-memory verification snapshot ID from the verifier version and complete validated intent/offer via deterministic sorted-key compact JSON and SHA-256; reject non-finite JSON. Changed evidence, merchant, amount, intent, or verifier version changes identity. This reference is distinct from the later approved proposal digest and is not persisted or trusted as authorization.

### Alternatives considered
- Let a match score, truthiness coercion, or listing instruction override mandatory failures.
- Treat absent evidence as PASS or automatically infer facts from prose.
- Give UNKNOWN preferences credit, make preferences block mandatory PASS, or assign 100 percent when no preferences exist.
- Implicitly implement financial policy or interpret query text within attribute verification.
- Generate random snapshot IDs for otherwise identical deterministic results.

### Why
Three-state evidence-backed comparisons satisfy the requested deterministic behavior while preserving uncertainty and the separation between purchase fit and financial authority. Explicit preferred checks explain scoring; content-derived snapshot references make evidence changes detectable for later binding.

### Consequences
The planned hotel fixtures now exercise mandatory PASS, FAIL, and UNKNOWN, with preference-only differences independently scored. Known mismatches cannot become matches when evidence is removed, and numeric/boolean coercion cannot invent compliance. Unsupported complex predicates need later handling. Literal string matching is intentionally strict. A semantic PASS does not become available merely because evidence text exists; all current checks are deterministic comparisons against structured data.

### Constraints / assumptions
The service assumes canonical backend offer sourcing; recorded excerpts do not independently establish truth. Budget, currency eligibility, quantity, merchant rules, and approval are not implicitly verified by this service and remain responsibilities of later policy/checkout stages; specific supported attributes such as nights can be explicitly required. No new routes, persistence, semantic matching, audit events, or payment execution are implemented. Verification PASS is never payment authority. No historical decision body is rewritten.

### Related files
- `backend/app/services/verifier.py`
- `backend/app/schemas/domain.py`
- `backend/tests/test_verifier.py`
- `docs/verification.md`
- `PLAN.md`
- `ARCHITECTURE.md`

### Supersedes / superseded by
None. Implements D-003 and D-004; extends the D-021 result contract with preferred checks and a concrete verification snapshot format without implementing D-007 proposal digest generation.

## D-024 — Structured, source-checked intent parsing behind an async interface
Date: 2026-11-11
Status: Superseded in part by D-033 (HTTP authentication and source-role checks only)

### Context
The intent-parser stage must convert purchase language to typed intent while preserving mandatory/preferred constraints, rejecting missing or unlimited budgets, and keeping probabilistic extraction outside financial authority. Tests must run without credentials or paid model calls.

### Decision
Define an async IntentParser protocol with OpenAI Responses strict structured-output and deterministic exact-query fake implementations. Use a closed intermediate Pydantic schema with nullable uncertainty fields and quoted attribute/money lists, then validate and convert to PurchaseIntent. Preserve the original query, separate required/preferred maps, reject duplicate/overlapping attributes, and check explicit role wording in exact source quotes. Keep hotel rooms and quantity consistent. A NEEDS_CLARIFICATION result never yields partial or invented intent.

Require a quoted finite total budget and one explicit supported currency. Initially support USD/EUR/CHF/GBP (two decimals) and JPY (zero), with no currency inference from ambiguous symbols, exchange conversion, or per-night repricing. Check money quotes against source text and convert written decimal amounts to integer minor units exactly; never use float conversion or round fractional minor units. Require a bounded quoted approval threshold when specified; otherwise use conservative zero rather than infer permission to spend. Parsed limits remain proposals and never modify active policy.

Expose POST /v1/agent/parse. Instantiate the real provider lazily with backend-only OPENAI_API_KEY and explicit OPENAI_MODEL, a 20-second timeout, zero automatic retries, no tools, and store=false. Return typed clarification/unavailable/invalid-output errors without raw provider data. Health/catalog run without credentials; no production fake fallback exists. Pin the official OpenAI SDK and its runtime dependencies, including the current httpx2 stack, which also resolves the prior TestClient deprecation warning. Add 15 synthetic gold prompts, exercised by fake and real-SDK mocked paths plus adversarial tests.

### Alternatives considered
- Parse free-form provider prose or send open dictionary schemas directly to strict structured output.
- Infer unlimited/high budgets, default currency, or automatic approval when user data is absent.
- Let the model convert money with floating-point values or accept invented source amounts.
- Couple the API directly to a provider or use fake/demo output when credentials fail.
- Require live credentials and paid calls for deterministic regression tests.

### Why
The interface isolates provider behavior, the closed intermediate format fits strict structured output, and server-side source checks plus exact money conversion prevent unsafe defaults and common extraction inconsistencies. Conservative missing-threshold handling preserves review rather than inventing spending authority. Fake and SDK-mock tests verify wiring and validation without conflating gold responses with live model accuracy.

### Consequences
The Intent task-board items now have implementation/test evidence, and the parse endpoint is available when configured. Missing/ambiguous user data requires clarification; unsupported currency/format cases do not receive guessed values. Additional supported currencies and providers need explicit conversion/contract tests. To reduce temporary VFS disk use, backend source/fixture copies occur before dependency installation, so source changes invalidate the dependency-install cache. Production deployment needs valid backend credentials and a structured-output-capable model; managed proxies may require a runtime public CA mount. Natural-language meaning can still be misinterpreted or omitted, so parsed intent remains untrusted, must be reviewed/revalidated, and cannot authorize payment.

### Constraints / assumptions
No live model evaluation was performed; responses in tests are synthetic gold fixtures or mocked HTTP. Source quote/role checks constrain output but are not a proof of complete semantic fidelity. No financial policy, approval, reservation, or payment service is implemented, and no payment credentials are exposed. Application threshold zero never substitutes for PayPal buyer authorization. Local Uvicorn requires environment variables to be set explicitly; Compose passes them only to the backend. Provider retention beyond the requested store=false behavior is not independently asserted.

### Related files
- `backend/app/services/intent_parser.py`
- `backend/app/schemas/intent_parser.py`
- `backend/app/api/agent.py`
- `backend/app/main.py`
- `backend/tests/test_intent_parser.py`
- `fixtures/intent_prompts.json`
- `backend/requirements.txt`
- `.env.example`
- `docker-compose.yml`
- `docs/intent-parser.md`

### Supersedes / superseded by
Superseded in part by D-033 for HTTP authentication and source-role checks; other D-001/D-017/D-008 parsing decisions and credential-free health/catalog startup remain in force.

## D-025 — Pure policy evaluation over explicit backend authority snapshots
Date: 2026-11-11
Status: Accepted

### Context
The policy stage needs final deterministic financial eligibility without letting parsed intent, model confidence, browser values, or human approval override hard limits. It precedes persistent policy/ledger/approval/payment services and must remain independently testable without side effects.

### Decision
Implement evaluate_policy as a pure synchronous function over canonical PurchaseProposal, current FinancialPolicy, BudgetSnapshot, AttemptSnapshot, explicit timezone-aware evaluation time, and optional backend-verified ApprovalRequest. Require explicit caps/thresholds, allowlist, ledger totals/reservations, and CLEAR/DUPLICATE/UNKNOWN history; no authority values default permissively. Revalidate input records and reject inconsistent ownership/currency/time contexts.

Enforce the minimum requested/active/available hard ceiling and minimum requested/active review threshold. Deny incompatible currencies without comparing or converting their monetary numbers. Deny mandatory failures, known quantity mismatches, stale policy versions, fabricated/stale verification, duplicates, rejected/invalid approvals, and uncertain payment history. Recompute the current deterministic verifier result rather than trusting supplied PASS or preference scores. Require review for mandatory UNKNOWN, missing snapshots/quantity evidence, unallowlisted merchants, threshold excess, and pending/expired approvals. Check canonical hotel rooms (otherwise quantity) separately from explicit attribute verification.

Allow only an exact, unexpired, already trusted approval record to resolve review, comparing all user/proposal/offer/merchant/money/currency/policy/snapshot/digest terms; it can never resolve hard denial. Keep DENY before REQUIRE_APPROVAL before ALLOW_ELIGIBLE_FOR_CHECKOUT, with stable unique reason codes and explicit budget currency in results. Add VERIFICATION_INVALID, PAYMENT_STATE_UNKNOWN, APPROVAL_PENDING, APPROVAL_REJECTED, APPROVAL_INVALID, and APPROVAL_GRANTED codes to the existing vocabulary. No LLM or tool is consulted in this decision path, and no public endpoint accepts authority records.

### Alternatives considered
- Use parsed budgets/thresholds as active policy or trust LLM-generated policy decisions.
- Treat missing history, missing balances, or absent allowlists as eligible defaults.
- Let preference confidence or approved status alone override hard denial or expired/changed consent.
- Compare values across currencies or label an offer-currency amount and ledger balance with one currency.
- Add policy storage, digest generation, approval transitions, reservations, or payment execution during this pure-service stage.

### Why
Explicit trusted inputs and deterministic precedence preserve financial authority in backend code. Recomputed verification and exact approval comparisons detect stale or fabricated records; independent hard limits prevent prompt-based limit inflation. A pure function can be regression-tested before side-effecting integrations exist, with honest boundaries around races and persistence.

### Consequences
The demo yields eligible/review/denied outcomes with explainable codes, and all authority inputs/clock are explicit. The additive optional PolicyDecision.budget_currency preserves older constructors while service outputs always label the balance correctly. Human approval can resolve UNKNOWN/merchant/threshold review but cannot legitimize failure, duplicate/uncertain execution, or insufficient funds. Only the existing deterministic verification version is accepted; semantic verification needs a later trusted integration. Read-only duplicate/approval checks exist, but durable uniqueness, consent authentication, digest computation, atomic reservations, and before-capture integration remain unfinished.

### Constraints / assumptions
Authority snapshots and approvals must originate in trusted backend loading/authentication, not an LLM or browser DTO. Policy changes must advance immutable versions. Availability is before the proposed reservation, not proof that funds were reserved. Stale snapshots and concurrent requests require transactional handling later. A supplied digest is compared, not calculated/authenticated here. Eligibility never substitutes for supported merchant/provider state, PayPal buyer approval, or capture confirmation. Invalid authority contexts stop explicitly instead of yielding permissive outcomes.

### Related files
- `backend/app/services/policy.py`
- `backend/app/schemas/policy.py`
- `backend/app/schemas/domain.py`
- `backend/tests/test_policy.py`
- `docs/policy.md`
- `PLAN.md`
- `ARCHITECTURE.md`

### Supersedes / superseded by
None. Implements D-002, refines D-006/D-009/D-015 read-only policy gates, and integrates D-023 verification; D-007 digest generation, approval workflows, and transactional payment controls remain separate stages.

## D-026 — Canonical proposal hashes and service-owned expiring approval records
Date: 2026-11-11
Status: Superseded in part by D-033 (proposal digest format only)

### Context
Approvals must authorize exact canonical terms, expire, and stop being usable when terms change. Comparing two caller-supplied SHA-shaped strings is insufficient, and old approvals must not revive after a change is reverted or a newer review is rejected. The repository currently has no database/authenticated-user HTTP layer.

### Decision
Implement proposal binding with compact sorted-key ASCII-escaped JSON, UTF-8, and SHA-256. Bind format version, proposal ID, canonical UTC creation timestamp, user, offer, merchant, integer amount, currency, policy version, and current verification snapshot ID. Recompute/validate the full deterministic verification result first. Keep stored digest/policy reports out of the hashed payload. Regenerate and constant-time compare before consuming a binding; extend pure policy evaluation to reject nonmatching non-null digests and INVALIDATED approvals.

Implement an internal InMemoryApprovalService owning canonical proposal/request copies. Backend-only canonical writes recompute hashes, use expected-digest compare-and-swap for changed updates, and permanently invalidate outstanding grants. User operations require a trusted authenticated actor ID, and approve/reject operate by server-generated request ID rather than accepting caller-authored approved objects. Preserve exact user/offer/merchant/money/currency/policy/snapshot/digest fields. Default expiry is 10 minutes with positive backend-configured TTL capped at one hour; retries cannot extend it and expiry is inclusive. Explicit timezone-aware times must not move backwards.

Add INVALIDATED to application approval states. Allow only a current unexpired PENDING record to be decided once. New reviews supersede prior grants; reverting terms or ignoring a newer request never restores consent. Revalidate canonical records plus current financial policy at approval and checkout; policy version changes revoke old grants, and approvals never override hard denial. Use process-local locking for the reference workflow and return copies to prevent external mutation.

### Alternatives considered
- Trust client-supplied digests, APPROVED flags, user IDs, or modified returned records.
- Hash only amount/merchant, omit proposal identity, or concatenate ambiguous strings.
- Extend expiry on request retry, reuse superseded grants, or reactivate consent after a change is reverted.
- Expose unauthenticated approval endpoints or introduce a full database/auth/payment stack during the requested binding stage.

### Why
Canonical hashing detects changed terms and binds verified intent/evidence to consent. Service-owned lifecycle state prevents plain digest equality from reviving revoked or superseded grants. Internal reference services can implement and test the requested invariants without pretending missing authentication/persistence exists or exposing financial actions to an LLM.

### Consequences
Canonical hashes, exact approval bindings, request creation, one-time decisions, expiry, invalidation, and checkout revalidation now have regression evidence. Pure policy no longer accepts a fabricated matching pair of SHA-shaped hashes. HTTP approval endpoints and production persistence remain unfinished, and the in-memory store fails closed on restart. Canonical data updates must flow through the service; durable implementations must preserve invalidation/CAS/ownership semantics. Locking here does not reserve money or prevent cross-process duplicate capture. No LLM calls, live buyer actions, or payment execution occur.

### Constraints / assumptions
Backend loaders and authentication must establish canonical data/actor provenance; the hash is neither a signature nor consent. Active policy/budget/history inputs remain trusted server records. Only explicit buyer actions may call the approve method; agents cannot grant consent. Current policy is rerun immediately before any future irreversible action, and PayPal buyer authorization remains separately mandatory. Audit storage, durable transactions, public endpoints, and deployment wiring remain later integration work. Prior historical decision entries are unchanged.

### Related files
- `backend/app/services/proposal_binding.py`
- `backend/app/services/approvals.py`
- `backend/app/services/policy.py`
- `backend/app/schemas/domain.py`
- `backend/tests/test_approvals.py`
- `backend/tests/test_policy.py`
- `docs/approvals.md`
- `ARCHITECTURE.md`

### Supersedes / superseded by
Superseded in part by D-033 for digest format only; D-007/D-006/D-025 binding/approval lifecycle decisions remain in force and durable authorization remains separate work.

## D-027 — Exact nine-state event-driven payment transition graph
Date: 2026-11-11
Status: Accepted

### Context
The requested payment-state stage specifies nine states and requires illegal transitions to be rejected. Earlier schema planning included an extra VERIFYING member but no transition implementation. State progression must not skip current policy after approval, reopen terminal payments, or treat ambiguous capture results as failed/retryable.

### Decision
Use exactly the requested nine PaymentState values and remove unused VERIFYING. Centralize legal backend-event transitions in a nested immutable table. Provide validated state/event resolution, immutable reachability introspection, and a PaymentIntent state-only update helper with an optional local expected-state check. Preserve every binding, payment identity, creation time, approval metadata, and idempotency key. Reject unknown/removed values, unsupported event/source combinations, same-state transitions, and terminal-state exits.

Application approval returns AWAITING_APPROVAL to POLICY_CHECK for fresh checks before checkout readiness. Pre-capture states can cancel/fail or return to policy as explicitly allowed. CAPTURE_PENDING can resolve from confirmed capture success/failure or become PENDING_PROVIDER on uncertainty. PENDING_PROVIDER only exits through conclusive reconciliation success/failure; it cannot directly retry capture, cancel, reset, or accept a generic capture failure. SUCCEEDED and FAILED are terminal. Backend/provider event provenance is a prerequisite, not inferred from enum values.

### Alternatives considered
- Retain the earlier extra VERIFYING vocabulary despite the explicit nine-state request.
- Permit arbitrary target assignments, mutable transition maps, generic failure on timeout, or capture retry from uncertain state.
- Move directly from application approval to checkout without rechecking policy.
- Implement provider mapping/capture, durable persistence, financial reservations, or public transition endpoints in this graph-only stage.

### Why
A small explicit event-driven graph makes legal progression reviewable and exhaustively testable. Terminal locks and reconciliation-only uncertainty handling preserve the existing payment-safety boundaries. Removing an unused state follows the user's current contract; the engine remains independent of payment SDKs while retaining the requested AWAITING_PAYPAL_BUYER label.

### Consequences
All nine states have enforced legal transitions and tested negative paths, including the full state/event and state-pair matrices. Transition helpers return validated copies without changing bound terms or idempotency. The old VERIFYING value is invalid; no repository payment database requires migration. Local stale-state checks do not replace durable compare-and-swap, and repeated provider callbacks need future handler deduplication. Graph legality is not user approval, financial authorization, provider verification, reservation, or capture; those gates remain coordinator/adapter responsibilities.

### Constraints / assumptions
Only trusted backend components may emit transition events after establishing their business/provider facts. LLM/browser data and unverified webhooks cannot directly set authoritative state or supply success evidence. The library has no I/O, system clock, SDK client, financial side effect, or public API. Later execution must atomically persist state/audit and revalidate current policy/bindings/consent before irreversible action. Existing in-memory approval/persistence limitations are unchanged. D-021's status/supersession metadata is updated; its historical decision body is preserved.

### Related files
- `backend/app/services/payment_state_machine.py`
- `backend/app/schemas/domain.py`
- `backend/tests/test_payment_state_machine.py`
- `docs/payment-state-machine.md`
- `ARCHITECTURE.md`
- `CODEX_PROMPTS.md`

### Supersedes / superseded by
Supersedes D-021's VERIFYING vocabulary choice only; other D-021 contracts remain in effect. Implements D-016 centralized transitions and D-010 capture-uncertainty progression without implementing provider reconciliation itself.

## D-028 — Backend-only Sandbox adapter with verified observations and conservative recovery
Date: 2026-11-11
Status: Accepted

### Context
Stage 9 requires OAuth, Orders v2 create/status/capture, idempotency and state mapping. Provider responses are untrusted until exact bindings are checked; HTTP success or COMPLETED order alone cannot prove capture success. An ambiguous capture must not trigger another financial action.

### Decision
Implement an internal async httpx2 Sandbox adapter with server environment credentials, SecretStr handling, cached OAuth, fixed HTTPS Sandbox origin, redirects disabled, safe errors and no public capture/LLM interface. Accept one CAPTURE purchase unit in USD/EUR with strict integer minor units and an explicit backend-resolved real Sandbox payee/reference. Verify order and capture amount/currency, payee, reference and expected order ID. Require authenticated provider APPROVED preflight before capture. Use deterministic operation-specific UUID PayPal-Request-Id headers from caller-owned persistent keys. Treat mutation transport/HTTP/malformed/binding errors conservatively as uncertain, with no automatic retry. Expose GET reconciliation, retain open attempted captures as PENDING_PROVIDER, and require exact full final COMPLETED capture evidence for success. A process-local uncertainty guard supplements, but does not replace, durable coordinator state. Keep checkout integration in the next requested stage.

### Alternatives considered
- Expose credentials/capture authority to browser or LLM, permit live/custom API origins, or follow redirects.
- Trust browser callback, order COMPLETED alone, partial captures, or mismatched payee/amount.
- Retry POST automatically, use a new key per retry, or treat any HTTP error as terminal financial failure.
- Implement all currencies, provider refunds, persistence, authenticated checkout routes, or buyer UI in this adapter stage.

### Why
A narrow backend boundary preserves financial authority and makes exact provider semantics testable through real HTTP serialization with a mocked transport. Conservative uncertainty avoids duplicate payment and false success. USD/EUR cover current demo fixtures without unsupported currency exponent assumptions. Official PayPal documentation and API schema inform endpoint/status behavior.

### Consequences
OAuth/create/status/capture and state observations are implemented and mock-tested without live payments or new dependencies. Some definite-looking HTTP refusals remain uncertain until reconciliation/operator review. The adapter cannot guarantee durable idempotency, authorization, supported merchant mapping or cross-process concurrency by itself. Unknown-create recovery may lack an order ID and requires a future explicit recovery procedure; provider request retention is finite. Live Sandbox setup, buyer checkout, durable recovery/audit and transactional coordination remain incomplete.

### Constraints / assumptions
Only trusted authenticated backend coordination may invoke execution after current policy, proposal/approval, canonical merchant, funds and history checks. Caller persists immutable operation-key/terms/provider IDs and enforces unique atomic execution, including PENDING_PROVIDER across process restart. Synthetic offers are not live merchant integrations. No live payment or provider credential readiness is claimed. Adapter observations must be translated into legal state-machine events; they do not mutate authoritative PaymentIntent records.

### Related files
- `backend/app/services/paypal.py`
- `backend/tests/test_paypal.py`
- `docs/paypal.md`
- `.env.example`
- `docker-compose.yml`
- `backend/app/services/payment_state_machine.py`
- `STATUS.md`
- `TASKS.md`

### Supersedes / superseded by
None. Implements the adapter portion of D-005/D-009/D-010 and preserves D-027 reconciliation-only transitions. Durable checkout coordination remains pending.

## D-029 — Durable checkout claims with a final canonical authority gate
Date: 2026-11-11
Status: Accepted

### Context
Stage 10 must connect validated proposals to order creation, PayPal buyer consent and capture, and reload policy, approval and digest while reserving funds before capture. The existing approval authority is process-local, and there is no authenticated public checkout or durable ledger. Provider I/O must not allow duplicate execution, overspend or loss of uncertain reservations.

### Decision
Add an internal CheckoutService and a local-file SQLite checkout ledger using built-in Python, WAL/FULL synchronous transactions, a unique checkout per proposal, stable operation keys, immutable provider terms, atomic budget holds/state/audit and exactly-once settlement/release. Persist dispatch claims before provider I/O. Add an adapter callback that runs after provider approval/binding preflight and OAuth, immediately before capture dispatch. It reloads canonical authority, regenerates the digest, reruns deterministic policy with current ledger availability, checks current approval/expiry/reference and merchant mapping, then reserves and commits CAPTURE_PENDING atomically. Hold the process-local canonical lock through the claim commit, never through network I/O.

Expose identifier-only FastAPI checkout routes with extra financial/identity/approval fields forbidden. Leave authentication and service provisioning fail-closed (503) until a trusted server session/token adapter is installed; do not invent browser-header authentication. Reuse the existing in-memory approval service instead of silently treating persisted/browser snapshots as fresh authority. Lost canonical authority blocks new capture. Persisted attempted captures can reconcile against original immutable terms without rerunning permission for a financial action that already occurred.

Keep uncertain holds across errors/cancellation/restart; reconciliation performs GET only and never interprets an open order as capture failure. Unknown create outcomes stop without automatic retry. Record an already captured exact order discovered at preflight as provider accounting, including an explicit external-capture audit event, without dispatching another capture. Local cancellation does not claim to void a PayPal order.

### Alternatives considered
- In-memory budget holds, random retry keys, unguarded check-then-capture, or trusting browser amount/merchant/success callbacks.
- Start a new PostgreSQL deployment or replace the entire canonical approval/authentication system in this integration stage.
- Expose permissive user headers or constant-identity production routes to make checkout appear configured.
- Release uncertain holds on timeout, rerun capture on restart, or suppress confirmed past spending because current approval/policy changed.

### Why
SQLite provides reproducible durable transactions without new services/dependencies for this single-host reference. A final gate after provider I/O closes the tested stale-proposal/approval/budget gap, while unique claims and ledger serialization prevent duplicate capture and concurrent overspend. Failing closed preserves missing authentication/authority boundaries. Accurate reconciliation accounts for original provider outcomes without authorizing a new purchase.

### Consequences
Backend checkout and guarded HTTP contracts are implemented with real-adapter mocked HTTP, persistent holds/audit and race/restart cases. SQLite is an interim single-host ledger, not the preferred production PostgreSQL deployment. Canonical proposals/approvals remain in memory; public deployment and durable multi-worker authority require further work. Uncertain create/capture may require operator recovery and can retain funds indefinitely. Each proposal has at most one checkout, even after failure; changed/replaced consent uses a fresh canonical proposal. Buyer UI, live Sandbox acceptance, full audit timeline and real authentication remain pending.

### Constraints / assumptions
Only trusted backend code configures accounts/policy, maps supported Sandbox payees, registers canonical offers/proposals, supplies authenticated actors and installs dependencies. The local database and its directory/backups must be protected and persist across restart; SQLite is not placed on a network filesystem. Approval writers must preserve the documented ledger-then-canonical lock order. Authorization is committed at a specific point before dispatch; later revocation cannot undo a committed request. All hotel data remains synthetic. No live provider call or fully configured public checkout is claimed.

### Related files
- `backend/app/services/checkout.py`
- `backend/app/services/checkout_store.py`
- `backend/app/services/approvals.py`
- `backend/app/services/paypal.py`
- `backend/app/schemas/checkout.py`
- `backend/app/api/checkout.py`
- `backend/app/main.py`
- `backend/tests/test_checkout.py`
- `docs/checkout.md`
- `TASKS.md`
- `STATUS.md`

### Supersedes / superseded by
None. Implements checkout portions of D-002/D-006/D-007/D-009/D-010 and integrates D-025 through D-028. PostgreSQL preference and in-memory canonical-authority limitations are not superseded.

## D-030 — Ryuk identity and evidence-first casebook interface
Date: 2026-11-11
Status: Accepted

### Context
The frontend request names the product Ryuk and requires a restrained investigative notebook rather than generic AI-startup styling, while preserving existing financial authority and showing evidence before payment.

### Decision
Use visible RYUK/Ryuk branding, near-black paper surfaces, original abstract mountain line art, serif headings, monospace records, thin borders and sparse deep red. Use no franchise assets or gradient/glass effects. Present one casebook flow: instruction, backend-parsed intent, first three candidate records with optional expansion, evidence matrix, deterministic verdict, exact approval, actual SDK checkout, backend payment record and audit. Label fixture data and demo-payee/no-booking scope. Display backend evidence counts and separate preference percentages instead of inventing an overall match/confidence score. Keep backend state the only source of payment confirmation. Preserve internal modules/API paths/database/state/environment identifiers.

### Alternatives considered
- Generic rounded AI dashboard/gradient hero or copied franchise artwork.
- Recompute policy or invent match scores, evidence, audit times or successful payment in the browser.
- Rename internal contracts for branding or show every candidate at full length on the primary demo path.

### Why
The requested mood supports a clear three-minute inspection of intent, evidence and authority without compromising existing boundaries. The visible shortlist emphasizes eligible/review/denied examples while retaining other backend records.

### Consequences
The frontend has a responsive custom casebook, accessible native review/sign-in dialogs and explicit blocked/pending/provider-unavailable states. It depends on real backend results; missing configuration cannot masquerade as a successful demo. Live SDK/buyer timing and acceptance still need verification.

### Constraints / assumptions
Preference FAIL does not become a mandatory denial. Every displayed PASS comes from backend checks/evidence. Checkout callbacks cannot declare success. Historical planning/decision text and internal AgentPay identifiers are not mass-renamed. Mocked browser validation does not satisfy the user's real Sandbox acceptance criterion.

### Related files
- `frontend/app/page.tsx`
- `frontend/app/globals.css`
- `frontend/app/layout.tsx`
- `frontend/components/paypal.tsx`
- `frontend/lib/contracts.ts`
- `frontend/lib/api.ts`
- `frontend/tests/e2e.mjs`
- `docs/frontend.md`

### Supersedes / superseded by
None. Implements the requested Ryuk product identity and UI over D-003/D-004/D-012/D-018; financial rules remain unchanged.

## D-031 — Opt-in private demo session and thin same-origin integration seams
Date: 2026-11-11
Status: Accepted

### Context
The frontend cannot safely integrate missing proposal/approval/audit/workspace routes by inventing browser authority or using the previously test-only constant actor. The current stage permits the smallest missing backend integration endpoints while preserving architecture and payment rules.

### Decision
Add an explicitly enabled single-buyer private Sandbox workspace: backend-only password (minimum 16 characters), scrypt/constant-time verification, five attempts per client/minute, random hashed server-side session token, 20-minute HttpOnly/SameSite=Strict cookie, logout revocation and exact configured origin checks on mutations. Keep demo mode off by default; no unsigned identity header authenticates. Proxy an allowlist of backend routes through Next server code with cookies, origin checks, no caching/redirects and safe errors. Only the public PayPal client ID reaches the SDK, never its secret.

Add thin authenticated request/proposal/select/approval/audit/workspace adapters around existing parser, catalog, verifier, policy, approval and checkout services. Browser requests carry query or identifiers/decision, not structured financial authority. Preserve active backend caps and immutable payment terms. Seed a trusted demo account/policy once, retain its durable ledger across restart, configure supported Sandbox mappings only on the backend, and provide a protected persistent Compose volume. Canonical proposal/approval/early audit remain process-local; no core persistence/security refactor is made. Test-only provider/model hooks stay outside production startup and image inputs.

### Alternatives considered
- Expose checkout without authentication, choose users from browser JSON/headers, or add a constant production actor.
- Duplicate policy/verification, synthesize intent/evidence/payment success in the UI, or silently switch to fake providers when credentials are absent.
- Introduce a broad production identity service, new architecture or durable canonical-store migration in the frontend stage.

### Why
These are the integration seams needed for a usable private demo with explicit authentication and existing backend financial authority. Default refusal and honest unavailable states preserve prior invariants without claiming multi-user production readiness.

### Consequences
Authenticated browser requests can use the real existing services and SDK path; mocked HTTP/browser tests cover the full interaction. A private operator must configure password/origin/providers. Sessions and canonical authority are process-local and one-worker/single-buyer scoped; this does not establish production auth or durable multi-worker authorization. Actual provider account/SDK/transaction acceptance remains blocked by unavailable shared credentials and must not be marked complete.

### Constraints / assumptions
The operator protects private `.env`, database directory/volume and credentials, enables secure cookies for HTTPS, and configures a supported Sandbox seller and buyer. A local file on the user's computer is not automatically present in this cloud workspace. Source review and mocked execution are distinct from a real Sandbox transaction. Step 12 is not started by this implementation.

### Related files
- `backend/app/services/session.py`
- `backend/app/services/provisioning.py`
- `backend/app/services/workspace.py`
- `backend/app/api/workspace.py`
- `backend/app/api/checkout.py`
- `backend/app/main.py`
- `frontend/app/api/ryuk/[...path]/route.ts`
- `backend/tests/test_workspace.py`
- `backend/tests/frontend_server.py`
- `.env.example`
- `docker-compose.yml`
- `backend/Dockerfile`
- `docs/frontend.md`

### Supersedes / superseded by
None. Implements the missing private-demo auth/provisioning seam in D-029, retaining its ledger and canonical-authority constraints. No production identity or live acceptance decision is implied.

## D-032 — Setting-specific startup diagnostics without private values
Date: 2026-11-11
Status: Accepted

### Context
A user's local Docker backend exited during demo provisioning, but the catch-all startup message hid which setting failed. The provided traceback cannot establish the actual invalid local value. The earlier prefix-based origin check also rejected valid HTTP loopback IP origins.

### Decision
Validate demo origin/password/cookie flag/seed budget/merchant/path before provisioning side effects and report a fixed setting name plus expected format, never its supplied value or raw exception. Classify SQLite/permission and password-hashing/TLS initialization failures safely. Parse origins as URLs: allow complete HTTPS origins and local HTTP localhost/127.0.0.1/::1 origins; reject credentials, paths, query/fragment and invalid ports. Retain exact-origin session checks, fail-closed startup, private environment configuration and all financial rules.

### Alternatives considered
- Continue using one opaque catch-all error and repeatedly guess at the user's configuration.
- Log environment values/raw validation exceptions or request a private `.env` upload.
- Disable authentication or replace invalid settings with permissive defaults.

### Why
Operators can correct the actual named setting without exposing credentials. Structural URL validation supports legitimate local device usage while preserving the browser origin boundary.

### Consequences
Startup failures become actionable and regression-tested; invalid configuration still prevents demo startup. This does not identify the user's existing local root cause until they run the updated image, nor establish live Sandbox acceptance.

### Constraints / assumptions
Diagnostic messages interpolate only code-owned descriptions, never environment contents. Existing account spending/holds are preserved; no database reset or permission bypass is introduced. Live Step 11 acceptance remains pending and Step 12 is not started.

### Related files
- `backend/app/services/provisioning.py`
- `backend/tests/test_provisioning.py`
- `docs/frontend.md`
- `STATUS.md`
- `TASKS.md`

### Supersedes / superseded by
None. Refines D-031 startup validation/diagnostics; authentication and payment-authority decisions are unchanged.

## D-033 — Mandatory review of model-derived intent and credential-safe HTTP boundaries
Date: 2026-11-11
Status: Accepted

### Context
Step 12 reproduced an unauthenticated billable parser route, mandatory-role evasion
through shortened source quotes, credential reflection in validation responses and
remote HTTPS startup accepting insecure session cookies. Quoted structured output
does not prove that every mandatory requirement or preference was preserved.

### Decision
Require the existing authenticated actor and exact mutation-origin gate before
initializing the parser for direct HTTP calls. Keep internal parser orchestration
separate from its authenticated HTTP wrapper. Return fixed input-free request
validation errors across the application. Refuse insecure cookies except for
validated local HTTP origins.

Check the enclosing source clause for explicit requirement-role wording. Because
this cannot prove semantic completeness, mark every model-derived workspace
proposal with a backend-owned `intent_review_required` flag. Pure policy always
requires application approval for these proposals, independently of the requested
or active monetary review threshold. Reuse existing owned, expiring, one-time
approval and checkout revalidation, rather than granting authority to the model
or adding another parallel consent mechanism. Display the original instruction,
parsed required/preferred values, quantity and requested limits in the exact-term
approval dialog; the buyer must reject omissions/changed meaning.

Advance canonical proposal digest format to `agentpay-proposal-v2` and include the
review flag. Existing verification snapshot already binds the complete original
query and parsed intent. Changing either interpretation or the review requirement
invalidates old consent. Old canonical authority is process-local and fails closed
on restart; persisted attempted payments continue GET-only reconciliation from
their original terms. No ledger migration, reset or capture retry is introduced.

### Alternatives considered
- Treat exact quoted/schema-valid model output as semantically complete.
- Add keyword heuristics and claim all natural-language requirements are preserved.
- Change the user's parsed monetary threshold to zero, obscuring the original request.
- Implement another approval store or put financial authority in the frontend/model.

### Why
Bound explicit human review closes the automatic authorization gap without pretending
the parser is a semantic oracle or rewriting spending limits. Existing deterministic
denials, PayPal buyer approval, reservations and provider verification remain mandatory.

### Consequences / constraints
Below-threshold model-derived offers initially show REQUIRE_APPROVAL, not automatic
eligibility. Model fidelity still needs user scrutiny and separate evaluation. This
is source/mock security review, not live Sandbox acceptance or production deployment.
All tests use isolated mock providers. Browser tests allocate new disposable ledgers
and never reset/delete existing records. Remaining resource limits, durable authority,
SQLite/provisioning/ACL assumptions and operator/provider recovery are documented.

### Related files
- `docs/security-review.md`, `STATUS.md`, `TASKS.md`
- `backend/app/api/agent.py`, `backend/app/main.py`
- `backend/app/services/intent_parser.py`, `backend/app/services/provisioning.py`
- `backend/app/schemas/domain.py`, `backend/app/services/policy.py`
- `backend/app/services/proposal_binding.py`, `backend/app/services/workspace.py`
- `frontend/app/page.tsx`, `frontend/app/globals.css`
- `backend/tests/test_security_review.py`, `backend/tests/frontend_server.py`
- `frontend/tests/e2e.mjs`

### Supersedes / superseded by
Supersedes D-024's unauthenticated parser HTTP boundary/quote-only role checks and
D-026's v1 digest format only; their other decisions remain in force. Adds mandatory
intent review to D-031 workspace orchestration and enforces its stated HTTPS-cookie
constraint. No prior historical decision body is rewritten. Step 13 is not started.

## D-034 — Resolve committed security merge conflicts without bypassing review
Date: 2026-11-12
Status: Accepted

WIP commit cde0d08 contained unresolved markers in seven files and duplicate review flags, enum members and validation handlers. Retain both security implementations' protections and regression suites, using one intent_review_required field/reason and one safe validation handler. Preserve full original/parsed intent digest binding, source-clause role checks, authenticated/rate-limited HTTP parser wrapper and separate internal orchestration. Preserve the readable review UI and combined browser assertions; keep the earlier hardening report separately.

Do not translate/revive incompatible in-memory consent or modify existing financial records. Durable uncertain captures retain original terms for query-only reconciliation. Add a source/runbook marker regression. Validation: 1,056 backend tests, frontend lint/type/build and 44 mocked browser assertions pass. No live provider call or deployment; buyer-approved acceptance remains pending.

## D-035 — Equivalent Groq transport schema and safe provider diagnostics
Date: 2026-11-12
Status: Accepted

Real Groq calls rejected ExtractedAttribute.value.anyOf because integer and number overlap. For Groq only, remove the redundant integer alternative; JSON Schema number includes integers, so the accepted JSON value set is unchanged. Preserve the shared application schema, strict Pydantic validation, source/role/money checks and digest-bound application review. Never downgrade to unstructured JSON or retry/fallback automatically.

Classify SDK HTTP errors by status into static code-owned authentication/access/model/rate/request/unavailable messages. Do not reflect provider body or exception text. Live gpt-oss-120b validation succeeded on the committed synthetic gold request; semantic completeness and buyer-approved payment remain separate acceptance gates. No payment operation was performed.

## D-036 — Constrain model monetary evidence instead of asking users to rephrase clear input
Date: 2026-11-12
Status: Accepted

The UI's valid built-in example produced currency-prefixed amount_text and quotes omitting the budget/threshold role cue. Keep strict backend validation. Explicitly prompt numeric-only tokens; restrict Groq transport money grammar and exact source-derived role/currency evidence candidates when available. These constraints narrow model outputs, do not infer missing money or raise policy limits, and never grant payment authority. Ambiguous/unsupported input still fails validation. Add UI-text/grammar/source-span regressions and verify the exact screenshot text live. No payment or semantic-completeness claim.

## D-037 — Preserve the PayPal SDK lifecycle until approval/cancel callbacks resolve
Date: 2026-11-12
Status: Accepted

A backend terminal/pending response updated React checkout state, unmounting the PayPal component and calling Buttons.close before onApprove returned. This can strand the popup/merchant overlay despite HTTP 200 responses. Keep the SDK component and nodes alive for that selected purchase; hide its action host once backend state no longer awaits buyer approval. SDK cleanup runs when leaving the purchase, not merely when a capture response arrives. Hold cancellation UI busy through its asynchronous callback.

No timers, forced window closure, capture retries, financial policy or provider-state shortcuts. Add a mock that detects close during callbacks; it reproduces the old bug and verifies success/pending/cancel paths after the fix. Frontend-only rollout preserves backend in-memory authority. A user's actual current payment still requires record/provider verification independently of transport HTTP status. No live payment made by these tests.

## D-038 — Operator acceptance export without financial side effects
Date: 2026-11-12
Status: Accepted

Use a local-only CLI and SQLite read-only/query-only snapshot to export allowlisted payment/order/capture references, amounts, recorded state and minimal audit. Check exactly one capture dispatch/settlement and a matching SETTLED reservation. Missing/incomplete evidence never triggers a new payment or provider query. Do not export credentials, actor identity, request text, idempotency keys or arbitrary audit detail blobs. Git-ignore receipt filenames and retain actual receipts privately. A standalone test receipt cannot certify a different user's UI transaction; UI timing and fresh provider verification remain distinct evidence.

## D-039 — Publish a scoped Sandbox source prerelease without resetting demo funds
Date: 2026-11-11 UTC
Status: Accepted

Tag v0.1.0-sandbox-demo as an annotated private-demo source prerelease only after exact-commit automated checks pass. Preserve the tested application; finalize operational/demo documentation and explicitly distinguish mocked tests, independently verified earlier standalone payment evidence, user-reported website receipt/container health, and unmeasured live timing. A spent demo budget uses clearly labeled prior evidence rather than resetting financial records or implying a fresh payment. The tag is not a production approval, deployed artifact attestation or promise of complete model semantics. Retain original security findings and add current mitigation/residual context without rewriting historical decisions.

## D-040 — Persist authority with the checkout ledger and expose safe recovery
Date: 2026-11-11 UTC
Status: Accepted

Runtime authority reloads a per-proposal persisted state into the existing approval state machine for each operation; schema/digest/identity checks and original consent expiry remain mandatory. Persist canonical/approval transitions and early audit in the existing protected SQLite ledger, and use the same store instance/transaction for final consent plus financial claims. Provider I/O stays outside synchronous transaction scopes. Expected pre-mutation consent failures preserve observed revocation/expiry; unexpected failures roll back. Process-local sessions still require login after restart.

Add owner-scoped paginated history and audit inspection, with existing GET-only provider reconciliation and no automatic recapture or replacement order. Backfill legacy checkout references for discovery, never reconstruct pre-upgrade lost consent. Additive startup tables preserve financial state; full versioned migrations/PostgreSQL, atomic provisioning, production identity/quotas and provider monitoring remain separate stages. D-033/D-038's process-local authority limitation is superseded for newly persisted records, not for pre-upgrade losses or their remaining security residuals. See docs/durable-authority.md.

## D-041 — Freeze Step 13 against durable runtime without expanding production scope
Date: 2026-11-11 UTC
Status: Accepted

Complete the CODEX_PROMPTS.md Step 13 scope with fresh tests, all six scenarios and current startup/walkthrough instructions. Publish v0.1.1-sandbox-demo as a tested source freeze after packaging checks; preserve v0.1.0-sandbox-demo. Durability was implemented separately before this freeze. Do not treat mock browser runtime as measured live-buyer acceptance or mark the remaining production backlog complete. Financial records and private receipts remain untouched.

## D-042 — Authenticate ingress-derived login rate-limit keys
Date: 2026-11-11 UTC
Status: Accepted

Next route handlers do not expose a trustworthy socket peer. Use a loopback-published Nginx ingress that overwrites identity headers, with no directly published frontend port. Next forwards its canonical IP assertion only in trusted-ingress mode, authenticated by a backend-only shared secret. Backend verifies the token and normalizes IPs; unverified requests use their direct peer, and Uvicorn proxy-header trust is disabled. Missing Compose channel config fails login closed. Keep financial actor authentication separate. Reclaim inactive limiter buckets without evicting live ones; shared/distributed limiter work remains separate.

## D-043 — Preserve definitive instrument-decline evidence and expose operator reconciliation
Date: 2026-11-11 UTC
Status: Accepted

Recognize only the authenticated capture endpoint's HTTP422 UNPROCESSABLE_ENTITY/single INSTRUMENT_DECLINED issue as explicit rejected-dispatch evidence. Persist the sanitized code and stable dispatch reference. Query the exact bound order before release, prioritizing actual completed/pending captures and retaining unknown outcomes. Existing atomic settlement/release and no-recapture rules remain authoritative. All other non-2xx/malformed/unknown outcomes remain uncertain.

Provide a local operator CLI with read-only bounded hold inspection and explicitly applied GET-only reconciliation, auditing operator label/reason and outcome. Never force release by age, user assertion or unrecorded historical error; no mutation retry/new purchase/refund. Legacy missing evidence and later external provider activity remain unresolved operational boundaries. See docs/operator-recovery.md.

## D-044 — Enforce nonce-based document scripts with PayPal nonce propagation
Date: 2026-11-11 UTC
Status: Accepted

Generate a cryptographic nonce for each document in Next proxy and overwrite untrusted nonce/CSP headers. Pass the policy into SSR and response; use async layout headers and no-store instead of static/shared nonce HTML. Production script-src uses nonce/strict-dynamic with self/PayPal/PayPalObjects compatibility fallbacks, no unsafe-inline/eval and no inline event attributes. The trusted SDK receives nonce and data-csp-nonce. Scoped resource sources and existing frame/base/object controls remain; inline styles are retained independently for dynamic UI/SDK use.

Browser regressions demonstrate blocked parser-inserted scripts/handlers and existing mocked checkout flows. Delegated trusted scripts and live SDK compatibility remain explicit boundaries; do not claim a mock proves live provider acceptance or that CSP neutralizes compromised authorized scripts. See docs/content-security-policy.md.

## D-045 — Retain validated requirement sources without reinterpreting intent
Date: 2026-11-12
Status: Accepted

Persist source associations already validated by the parser as optional PurchaseIntent requirement_sources entries with role/name/quote and Unicode code-point spans. Preserve provider extraction schema and all financial policy/consent checks. Validate complete, unique associations and exact unique source text whenever provenance is present. Do not fabricate provenance for legacy records.

Omit empty provenance from serialization so old persisted snapshot/digest inputs remain byte-compatible; the existing complete-intent snapshot/digest includes new provenance, binding the representation reviewed by the buyer. No SQL migration or financial record rewrite. Display original request and mandatory/preferred lists with escaped highlighted text and keyboard source links; merge overlaps only for rendering. Quotes demonstrate cited text, not semantic completeness. This supersedes the earlier presentation task-5 blocker only under the user's explicit backend/API authorization; README/diagram/packaging/migrations remain outside this turn.
