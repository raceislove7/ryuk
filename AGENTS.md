# AGENTS.md — Instructions for Coding Agents

## Project

You are working on **AgentPay**, a PayPal AI Hackathon project.

AgentPay transforms a natural-language purchase request into structured intent, searches trusted offers, verifies that the selected purchase matches the user's intent before payment, applies deterministic financial policy, and then uses PayPal Sandbox for a buyer-authorized checkout.

## Non-negotiable rule

**The LLM never has financial authority.**

The LLM may:
- parse intent,
- rank offers,
- summarize evidence,
- generate explanations,
- propose a purchase.

The LLM must never:
- call PayPal capture directly,
- alter policy limits,
- alter approved merchant/amount,
- mark a payment successful,
- treat missing evidence as confirmed,
- bypass user approval,
- store or expose payment credentials.

## MVP priorities

1. Correctness
2. Payment safety
3. Reproducible demo
4. Clear UX
5. Feature breadth

Avoid unnecessary microservices and abstractions.

## Required stack

Frontend:
- Next.js
- TypeScript
- Tailwind

Backend:
- Python
- FastAPI
- Pydantic

Data:
- PostgreSQL preferred

AI:
- structured output
- schema validation required

Payments:
- PayPal Sandbox
- Orders API v2

Testing:
- pytest
- frontend tests where useful
- Playwright if time permits

## Trust boundaries

Treat as untrusted:
- user natural language
- LLM output
- listing text
- browser-submitted amount
- browser-submitted merchant
- external tool output
- unverified webhook/provider events

Treat as authoritative only after backend verification:
- active policy
- remaining budget
- canonical selected offer
- canonical merchant
- canonical amount
- approval state
- PayPal provider status

## Payment invariants

Every payment attempt must:
- have a unique internal ID,
- use a stable idempotency key,
- bind to one canonical proposal,
- bind to exact merchant,
- bind to exact amount and currency,
- pass current policy,
- pass required approval,
- be revalidated before capture,
- be recorded in audit events.

Never blindly retry capture after an ambiguous network failure. Query provider state first.

## Verification rules

The verification engine returns only:
- PASS
- FAIL
- UNKNOWN

UNKNOWN is valid.

Do not use an LLM confidence score to override deterministic failures.

Every semantic PASS must include evidence.

## Coding standards

- Type public Python functions.
- Use Pydantic models at API boundaries.
- Use explicit enums for state machines.
- Centralize payment transitions.
- No secrets in source.
- No raw exception dumps with credentials.
- Prefer small services with clear interfaces.
- Write tests for security-sensitive code.
- Avoid magic numbers.
- Store money in integer minor units.

## Git behavior

Before a significant change:
1. inspect existing code,
2. identify affected files,
3. implement the smallest coherent change,
4. run relevant tests,
5. summarize changed behavior.

Do not rewrite unrelated code.

## When uncertain

For ambiguity involving:
- financial authority,
- authorization,
- PayPal API semantics,
- provider state,
- merchant identity,
- budget reservation,
- user consent,

choose the safer behavior and return REQUIRE_APPROVAL or stop with an explicit error.

Never invent provider behavior.


## Project documentation maintenance

After every meaningful implementation task:

1. Update STATUS.md to reflect actual repository state.
2. Append a new DECISIONS.md entry if the task introduced or changed a meaningful architecture, product, security, scope, or integration decision.
3. Never mark work complete unless the implementation exists and relevant tests pass.
4. Never rewrite historical decision entries. If a decision changes, add a new decision and mark the old one Superseded.
5. Keep TASKS.md and STATUS.md consistent.



## Stage execution

Work only on the currently requested stage.

Do not automatically begin the next stage after completing the current one.

At the end of each stage:
1. run relevant tests,
2. update STATUS.md,
3. update DECISIONS.md if needed,
4. report what was completed,
5. report blockers,
6. recommend the next stage,
7. stop and wait for the next instruction.


## Documentation maintenance

After every meaningful implementation task:

1. Update STATUS.md to reflect the actual repository state.
2. Append a DECISIONS.md entry only if a meaningful architecture, product, security, scope, or integration decision was made.
3. Never mark work complete unless the implementation exists and relevant tests pass.
4. Never rewrite historical decision entries. If a decision changes, create a new entry and mark the old one Superseded.
5. Keep TASKS.md and STATUS.md consistent.

## Stage execution

Work only on the currently requested stage.

Do not automatically begin the next stage.

At the end of each stage:
1. run relevant tests,
2. update STATUS.md,
3. update DECISIONS.md if needed,
4. summarize what was completed,
5. list blockers,
6. recommend the next stage,
7. stop.
