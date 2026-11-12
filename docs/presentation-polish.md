# Hackathon presentation polish — 2026-11-12

Historical presentation-only scope below. The user subsequently authorized and completed task 5 through the backend/API; see [requirement provenance](intent-provenance.md) and the latest STATUS.md. Tasks 6/7 remain separate.

Scope: presentation only, based on clean release worktree 1c49165. The separate older worktree was preserved. No backend, API contract, database schema, payment/approval/checkout/auth implementation, provider loader or CSP/security-header configuration changed. No dependencies added.

## Completed within existing response data

1. A persistent Sandbox/synthetic/no-real-money notice on the root layout and inside both dialogs; result text explicitly identifies a Sandbox record with no hotel booking.
2. Human explanations beside unchanged backend codes. The display map covers all 16 PolicyReasonCode values, including INTENT_REVIEW_REQUIRED, and has a generic unknown-code fallback. It never computes a policy decision or suppresses the original code. Unit coverage reads the actual backend enum to detect drift.
3. Settled/held/available bars read the existing workspace response. They do not infer availability, total new funds or settlement. Zero and exhausted budgets remain literal zero. Only illustrative bar bounds are clamped; numeric labels preserve backend values.
4. Loading messages use live status text and show additional guidance after 15 seconds. That timer changes presentation only; it never cancels/retries a request, clears busy state or changes payment status. Empty shortlist and request errors are explicit. Existing review/checkout controls keep their behavior, and pending/uncertain capture says not to press Pay again and to use the existing status control/saved activity. No new spinner or automatic retry was introduced.

New UI uses semantic notes/status/regions, labelled progress elements, unchanged keyboard-operable buttons/focus outlines, contrast-conscious colors and reduced-motion scrolling. The existing nonce/CSP remains intact.

## Stop boundary — task 5

`PurchaseIntent` (backend/app/schemas/domain.py) and the frontend Intent response contain query text and parsed attribute maps, not source quote-to-requirement associations. The parser validates quotes in its internal extraction then constructs PurchaseIntent without retaining those quote fields (backend/app/services/intent_parser.py). Offer verification evidence is catalog evidence, not a quote from the user's request.

Highlighting a source quote for each requirement would require retaining/exposing that provenance through backend contracts, or inventing frontend parsing. Neither is authorized. Task 5 was not implemented; existing original-versus-parsed review is preserved. Per the explicit stop-at-first-backend-change instruction, task 6 (README pitch/screenshot/quick start) and task 7 (architecture diagram) were not attempted. README and existing safety claims remain unchanged. No architecture/security/product-authority decision changed, so DECISIONS.md was not appended.

## Validation boundaries

All runtime testing uses the guarded fresh temporary fixture ledger, fake parser and intercepted/mock provider/SDK. Zero/exhausted budget and empty/error test cases modify only test response JSON. The slow-response test changes only the frontend test clock and an intercepted response; it must not issue another request automatically. No existing demo ledger/volume, credential values or live model/payment endpoint is accessed.

See STATUS.md for actual validation counts. Test screenshots are private temporary artifacts from isolated fixture data, not acceptance evidence of a real hotel or measured live three-minute run. No tag, commit, push or deployment is part of this pass.

## Final results and files

- Backend: 1,102 passed, zero skipped; unchanged count and unchanged backend files.
- Frontend: 22 presentation tests passed, zero skipped; lint/typecheck/production build passed. Node emits a non-failing module-type detection warning for the standalone TypeScript helper test; no package module mode/dependency change was introduced to suppress it.
- Production standalone Chromium: 81 assertions passed, desktop/mobile, existing nonce/CSP injection tests, zero/exhausted bar rendering, human denial copy, modal notice, slow response with one request, synthetic timeout error and empty shortlist. Basic screenshots inspected; not formal screen-reader/WCAG certification.
- Git whitespace and protected-file diff checks passed. Isolated fixture servers stopped; no live/provider/payment/deployment acceptance claimed.

Changed files: frontend/app/layout.tsx, frontend/app/page.tsx, frontend/app/globals.css, frontend/components/presentation.tsx, frontend/lib/presentation.ts, frontend/package.json, frontend/tests/presentation.test.mjs, frontend/tests/e2e.mjs, STATUS.md, TASKS.md and this document. Tests add no dependencies. README, DECISIONS.md and architecture diagrams are unchanged per the scope/stop boundary.
