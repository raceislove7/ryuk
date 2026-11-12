# Deterministic financial policy

`app.services.policy.evaluate_policy` is a pure synchronous backend function. It returns PolicyDecision with exactly DENY, REQUIRE_APPROVAL, or ALLOW_ELIGIBLE_FOR_CHECKOUT. It performs no I/O, reads no environment or system clock, invokes no LLM, and changes no input or financial state. An explicit timezone-aware `evaluated_at` makes expiry checks reproducible.

## Inputs and authority

Pass a canonical PurchaseProposal, current FinancialPolicy, BudgetSnapshot, AttemptSnapshot, evaluation timestamp, and optionally an already verified ApprovalRequest. The three new input contracts live in `app.schemas.policy` and are internal backend data, **not browser/model request DTOs**. Policy limits, allowlist, settled/reserved balances, history status, and approval records must come from trusted backend storage/configuration. All are explicit; no missing balance/history/allowlist is defaulted to a permissive value. Mutated model instances are revalidated.

The proposal contains the parsed intent (a proposal, not active policy), canonical selected offer, policy version, verification snapshot, and optional canonical digest. This pure service does not load/authenticate those records or create the digest; it now regenerates and verifies every supplied non-null digest through the [canonical binding helper](approvals.md). No policy HTTP endpoint is added until later proposal services can load canonical authority records safely. Never forward caller-supplied policy, budget, history, or approval flags into this function.

## Rules and precedence

1. Policy/proposal versions must agree. Stale proposals are denied with PROPOSAL_CHANGED.
2. Offer, intent, and active-policy currencies must agree. A mismatch denies without cross-currency amount/threshold comparisons or conversion.
3. In the matching currency, the hard ceiling is the minimum of requested maximum, active policy maximum, and available ledger funds. Available funds are `max(0, limit - settled - active reservations)` before this proposal. Exceeding any ceiling denies; an already overcommitted ledger denies even a zero-price offer. Zero is a literal zero ceiling, not unlimited.
4. The review threshold is the minimum of requested and active-policy thresholds. Amount strictly above that threshold requires approval; equality does not. Hard budget equality is allowed subject to all other rules.
5. Recompute deterministic verification from canonical intent/offer; reject a supplied result that differs from the current result. A known mandatory FAIL denies even when the caller omits its verification snapshot. UNKNOWN or a missing snapshot requires review. A fabricated PASS or preference score is not authority. Only the current deterministic verifier format is supported; a future semantic verifier needs an explicit trusted validation path.
6. Check quantity separately because the current verifier only evaluates explicit attribute maps. For hotels, match intent quantity against canonical `rooms`; for other categories use `quantity`. A known positive-integer mismatch denies, while absent/incompatible quantity or its missing evidence requires review. Boolean true cannot stand in for integer one.
7. A merchant absent from the current explicit allowlist requires review.
8. CLEAR history permits continued evaluation; DUPLICATE denies a new attempt; UNKNOWN denies until backend/provider reconciliation establishes the real state. Approval cannot resolve unknown payment history.
9. Honor only exact, current, already backend-verified approval records. Match user, proposal, offer, merchant, amount, currency, active policy version, verification snapshot, and canonical proposal digest. Missing digest/snapshot cannot validate a supplied approval; non-null digests must match freshly regenerated canonical hashes. Reject invalidated records, changed terms, rejected approvals, future-dated consent, or consent predating the proposal. Expired (including expiry equal to evaluation time) and pending records require renewed/completed approval. A valid APPROVED record may resolve evidence/threshold/merchant review, but never a hard denial.
10. DENY takes precedence over all review/approval conditions. Otherwise unresolved review yields REQUIRE_APPROVAL. Otherwise return ALLOW_ELIGIBLE_FOR_CHECKOUT.

For the planned USD fixture intent, with a 150000 hard cap, 130000 threshold, sufficient funds, known-clear history, and allowlisted synthetic merchants: hotel 001 is eligible, 002 requires approval, 003 is denied for budget, 004 is denied for required gym, and 005 requires evidence review. A complete approval bound to the current terms can resolve review on 002/005, but not budget denial on 003.

## Reason codes

| Code | Meaning |
| --- | --- |
| BUDGET_EXCEEDED | Requested/active maximum or available funds exceeded; or overcommitted ledger |
| CURRENCY_MISMATCH | Offer, intent, and active currency differ |
| REQUIRED_ATTRIBUTE_FAILED | Mandatory deterministic check or canonical quantity mismatch |
| MISSING_EVIDENCE | Mandatory UNKNOWN, absent verification snapshot, or unresolved quantity/evidence |
| APPROVAL_THRESHOLD_EXCEEDED | Price above the stricter review threshold |
| MERCHANT_REVIEW_REQUIRED | Merchant not currently allowlisted |
| DUPLICATE_ATTEMPT | Trusted history identifies a prior attempt for this proposal |
| PAYMENT_STATE_UNKNOWN | History is uncertain; backend/provider reconciliation needed |
| PROPOSAL_CHANGED | Policy version/approval-bound term differs, digest regeneration fails, or approval is INVALIDATED |
| VERIFICATION_INVALID | Supplied result is not the recomputed current snapshot/result |
| APPROVAL_PENDING | Supplied approval is not decided |
| APPROVAL_EXPIRED | Supplied approval is expired or marked EXPIRED |
| APPROVAL_REJECTED | Supplied approval was rejected |
| APPROVAL_INVALID | Approval creation/decision time is invalid relative to evaluation/proposal |
| APPROVAL_GRANTED | Exact current APPROVED record resolved review or accompanies eligible checkout |

Codes are unique in declared enum order, independent of map/set iteration. DENY reports hard and observed review reasons. REQUIRE_APPROVAL reports review reasons. ALLOW normally has no codes; with usable approval it reports APPROVAL_GRANTED. Current active policy version is returned. PolicyDecision includes offer amount/currency plus `budget_remaining_minor` and explicit `budget_currency`, so an EUR-denied offer never relabels a USD ledger balance as EUR. Older schema-only records can omit the additive budget_currency field; this service always supplies it.

Invalid/mismatched authority ownership, wrong ledger-versus-policy currency, evaluation before proposal creation, naive timestamps, and invalid/coercible money raise an explicit context/schema error. Such input is not a fourth financial outcome and never falls back to eligibility.

## Integration boundary

```
canonical proposal + current authority snapshots + explicit current time
  -> evaluate_policy(...)
  -> DENY / REQUIRE_APPROVAL / ALLOW_ELIGIBLE_FOR_CHECKOUT
```

Eligibility is conditional, **not capture permission or payment success**. The separate [internal approval service](approvals.md) now owns binding/request/decision/expiry state and invokes this pure evaluator. The evaluator regenerates non-null digests but does not mutate an allowlist/limit, reserve money, persist audit events, enforce unique payment attempts transactionally, query a provider, or execute payment. Pure history/balance checks cannot prevent races: later checkout must reload/revalidate current state, verify the canonical digest, reserve funds atomically, enforce durable uniqueness/idempotency, and obtain mandatory PayPal buyer authorization before capture. Active policy changes must advance the version so prior proposals/approvals are invalidated.

Verification snapshots and approvals passed here are assumed to have trusted provenance; shape and equality alone do not authenticate user consent. The synthetic merchant allowlist in tests is not a real PayPal merchant mapping. No provider acceptance, production payment support, or arbitrary-merchant checkout is claimed.
