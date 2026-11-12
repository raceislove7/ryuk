# Step 13 — demo-readiness acceptance

CODEX_PROMPTS.md defines this stage as all tests, six scenarios and docs/demo-script.md, with no new features. Those requirements pass at runtime source 8497325 plus documentation-only freeze changes.

| Check | Result |
| --- | --- |
| Complete backend suite | 1,082 passed |
| Eligible / approval required / budget denied / mandatory attribute denied / duplicate prevented / amount tampering prevented | All pass; named regressions in required-scenarios.md and demo-script.md |
| Frontend lint, TypeScript, production build | Pass |
| Standalone production browser suite | 51 mocked assertions pass, desktop/mobile and saved recovery |
| Browser suite elapsed time | 36.67 seconds; automated mocks only, not buyer-approved live timing |
| Ruff / pip consistency / Git whitespace | Pass |
| Docker/Compose | Both images built; separate credential-disabled project/ports/volume; both healthy; health OK and frontend HTTP 200 |
| Default financial access | Session configured=false/authenticated=false in isolated container smoke |
| Walkthrough/startup/limitations | Updated for v0.1.1-sandbox-demo and durable authority |

No application features, live payment, existing ledger deletion/reset or user-installation deployment occurred in this stage. Test fixtures create new ledgers; Docker rehearsal volumes are retained after stop. Original Sandbox release remains unchanged; the new source tag is a private demo freeze.

The user's successful website payment/receipt was reported at 0b24df8. Its private receipt remains outside Git. That evidence does not establish current deployment identity, a fresh provider query or a measured three-minute live run. Those remain separate live acceptance limits; production backlog is documented in release-notes.md and durable-authority.md.

Reproduce with the commands in startup.md and operations.md, using only the guarded fresh-ledger fixture for browser tests. Do not point fixture tests at the user's installation or pay again to demonstrate duplicate protection.
