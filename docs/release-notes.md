# v0.1.1-sandbox-demo — Step 13 freeze

Current source release includes durable canonical proposals/approvals, persisted early audit and owner-scoped saved recovery history. This Step 13 pass adds documentation only; no runtime features. Automated baseline at 8497325: 1,082 backend tests, all six required scenarios, Ruff/dependency checks, frontend lint/typecheck/build and 51 mocked browser assertions. Container and browser rerun results are recorded in STATUS.md before publication.

Startup and walkthrough target this new source tag. The earlier v0.1.0-sandbox-demo tag remains unchanged. This is a private single-buyer Sandbox demo; sessions still require reauthentication. Valid consent keeps its original expiry across restart, while legacy missing consent is never reconstructed. See [durable authority](durable-authority.md) for backup/upgrade details.

Remaining production work: multi-user identity, versioned migrations/atomic provisioning, quotas/retention, full script CSP/dependency remediation, terminal provider monitoring/refunds/reversals and operational recovery validation. No live-money deployment, real inventory/booking or independent current website-provider verification is claimed. User-reported local successful payment/receipt evidence remains at 0b24df8; it does not prove deployment of this new revision.

The walkthrough is prepared. A buyer-approved live run under three minutes remains unmeasured. Mock browser runtime is not a substitute. The previous release details below are historical and refer to its frozen source.

---

# v0.1.0-sandbox-demo

Private single-buyer Sandbox prerelease. Annotated source tag; not a production deployment, a signed container artifact or a real hotel-booking service.

## Included and validated

- Backend-only Groq/OpenAI intent parsing with strict schema/source validation and mandatory digest-bound human review of every model-derived purchase.
- Synthetic hotel evidence verification and deterministic budgets/mandatory requirements; separate application consent and PayPal buyer approval.
- Backend-owned Sandbox order/capture, SQLite atomic reservations, duplicate/concurrent protection, uncertainty retention and GET-only reconciliation.
- Integrated frontend with corrected SDK callback lifecycle, audit/result display and private read-only acceptance export.
- Automated baseline at application revision 31367ae: **1,070 backend tests**, Ruff/dependency consistency, frontend lint/typecheck/production build and **47 browser assertions** against isolated mocked model/SDK/provider. The five required scenarios pass a focused 32-test run. Subsequent release work changes documentation only; final tag is created after checks pass on its exact source commit.
- User-reported local evidence at 0b24df8: rebuilt backend/frontend healthy and exported website receipt checks_passed=true. The agent has not inspected the private receipt or independently queried this transaction's provider state. A separate USD100 Sandbox test was independently verified earlier; it does not substitute for the website transaction.

See [startup](startup.md), [walkthrough](demo-script.md), [acceptance matrix](required-scenarios.md) and [operations](operations.md). Private receipts, credentials and personal identifiers are excluded from the release.

## Remaining limitations and release gates

| Area | Residual limitation / required production work |
| --- | --- |
| Authentication and deployment | Single-buyer demo password and process-local sessions; not multi-user identity, scalable authorization or public abuse protection. Loopback only; public service requires reviewed identity, HTTPS/Secure cookies, trusted ingress quotas/timeouts and retention/concurrency limits. |
| Canonical authority and recovery | Proposals, approvals and early audit are process-local. Restart fails closed for new captures; checkout/holds persist. Durable canonical authority, owner-scoped history/discovery and operator orphan recovery are pending. Never reconstruct consent or clear holds by age. |
| Semantic correctness | Strict schemas, source quotes and mandatory review do not prove completeness or correct meaning. Unusual/ambiguous requests can fail or omit constraints; reject mismatches. No broad measured model-accuracy guarantee. |
| SQLite and operations | Single private local ledger; parent/backup ACLs and Windows permissions are operator responsibilities. Schema-versioned migrations, atomic provisioning, immutable policy versions and power-loss/restore validation need further work. No production multi-worker/database claim. |
| Provider lifecycle | Ambiguous outcomes can strand holds. Terminal external captures, refunds/reversals and ongoing authenticated monitoring are not comprehensively handled. Keep original references and reconcile; never blindly retry mutations. |
| Browser/dependencies | Baseline frame/base/object/referrer/MIME controls exist; full SDK-compatible script CSP remains pending. Development dependency advisories remain; historical audit counts are not a fresh release vulnerability scan. External SDK and provider availability remain dependencies. |
| Inventory and payment scope | Synthetic catalog only; no actual Google search, supplier booking/fulfillment, live-money payments, autonomous credential-based spending or additional payment rails. |
| Acceptance | User reports successful local website payment and receipt checks. No agent-observed current UI/provider verification, measured under-three-minute live run, reproducible image digest or production acceptance. |

The original [security review](security-review.md) retains exploit sequences and historical states. Its release addendum and [security hardening](security-hardening.md) distinguish later mitigations from residuals. Four confirmed High findings were fixed/contained; no Critical was confirmed in that review. This is not a guarantee that no further vulnerabilities exist.

## Tag and rollback boundaries

The tag identifies the reviewed source commit. Keep configuration, receipts and backups privately outside Git. Changing source revisions does not roll back provider activity or ledger schema/state. Do not restore an older database to undo a payment or retry a purchase. Follow operator reconciliation before any recovery. Timed live acceptance remains an explicit open item after this prerelease.
