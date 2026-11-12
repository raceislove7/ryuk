# Codex Prompt Sequence

Use these as separate tasks.

## 1 — Scaffold
Read PLAN.md, AGENTS.md, ARCHITECTURE.md.
Create Next.js + TypeScript + Tailwind frontend, FastAPI backend, Docker Compose, .env.example.
Do not implement AI or payments yet.
Acceptance: frontend boots, backend /health 200, no secrets.

## 2 — Domain schemas
Implement PurchaseIntent, Offer, CheckResult, VerificationResult, PolicyDecision, PurchaseProposal, ApprovalRequest, PaymentIntent.
Use integer minor units. Add tests.

## 3 — Hotel fixture catalog
Create fixtures/hotels.json with at least 6 synthetic offers and evidence fields.
Implement search/catalog service. Clearly label fixtures as synthetic.

## 4 — Verification engine
Implement deterministic required/preferred checks.
Mandatory false -> FAIL.
Mandatory evidence absent -> UNKNOWN.
All mandatory verified -> PASS.
Add tests.

## 5 — Intent parser
Add LLM-backed parser behind an interface.
Use structured output and Pydantic validation.
Preserve mandatory vs preferred.
Never infer unlimited budget.
Add deterministic fake parser for tests.

## 6 — Policy engine
Pure deterministic service.
Return DENY / REQUIRE_APPROVAL / ALLOW_ELIGIBLE_FOR_CHECKOUT.
Implement reason codes and tests.
LLM must not make final financial decision.

## 7 — Proposal binding + approval
Implement canonical proposal digest.
Bind approval to user, offer, merchant, amount, currency, policy version, verification snapshot.
Approval expires. Any bound-field change invalidates it.

## 8 — Payment state machine
Implement provider-neutral states:
CREATED, POLICY_CHECK, AWAITING_APPROVAL, CHECKOUT_READY, AWAITING_PAYPAL_BUYER, CAPTURE_PENDING, SUCCEEDED, FAILED, PENDING_PROVIDER.
Reject illegal transitions.

## 9 — PayPal Sandbox adapter
Implement OAuth, create order, get status, capture, idempotency, state mapping.
Never expose secret to browser.
Use env vars.
Add mocked HTTP tests.

## 10 — Checkout integration
Connect validated proposal -> PayPal order -> buyer approval -> capture.
Before capture: reload proposal, rerun policy, verify approval, verify digest, reserve budget.
Never trust browser amount/merchant.

## 11 — Frontend
Build request input, shortlist, requirement matrix, policy state, approval modal, PayPal checkout, result, audit timeline.
Optimize for a 3-minute demo.

## 12 — Security review
Review prompt injection, amount tampering, merchant substitution, duplicate capture, concurrent overspend, approval replay, expired approval, provider spoofing, ambiguous timeout, secret leakage.
List findings first. Then fix Critical/High with regression tests.

## 13 — Demo readiness
Run all tests.
Ensure scenarios: eligible, approval required, budget denied, mandatory attribute denied, duplicate prevented, amount tampering prevented.
Create docs/demo-script.md.
Do not add new features.
