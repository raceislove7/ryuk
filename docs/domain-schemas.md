# Domain schemas

Import contracts from `app.schemas`. These are Pydantic v2 data contracts. The [deterministic verifier](verification.md) now evaluates explicit structured attributes; the [pure financial policy service](policy.md) now evaluates explicit backend authority records. Canonical digest computation and an [internal in-memory approval workflow](approvals.md) are implemented. The [central payment transition graph](payment-state-machine.md) is implemented. Authenticated approval endpoints, durable persistence, financial/provider coordinator integration, and execution remain later stages.

| Contract | Purpose |
| --- | --- |
| PurchaseIntent | Query/category, currency, explicit budget and approval threshold, separate required/preferred attributes, quantity, notes |
| Offer | Canonical offer and merchant IDs, price, currency, JSON attributes, per-attribute evidence, source |
| CheckResult | Named requirement, PASS/FAIL/UNKNOWN, deterministic/semantic kind, supporting evidence, optional confidence, explanation |
| VerificationResult | Snapshot and offer IDs, required/preferred checks, aggregate mandatory status, preference percentage, missing mandatory evidence, explanation |
| PolicyDecision | Explicit outcome and reason codes, exact offer terms, remaining budget and its currency, policy version |
| PurchaseProposal | User/proposal identity, intent and selected offer, policy version, optional verification/decision/digest, creation time |
| ApprovalRequest | Exact proposal binding, request ID, approval status, creation/expiration/decision timestamps |
| PaymentIntent | Exact proposal binding, internal payment ID, explicit idempotency key, payment state, application approval state/reference |

## Validation rules

- All money fields end in `_minor` and require actual nonnegative integers. `118000` USD means USD 1,180.00. Floats (including `118000.0`), numeric strings, booleans, decimals, negative amounts, and null are rejected. No float conversion or rounding is performed.
- A missing budget or approval threshold is an error. Zero is a literal zero limit, not unlimited. Threshold must not exceed the hard budget. Quantity is a positive actual integer.
- Currency codes must be three uppercase ASCII letters. This checks shape only, not ISO membership, currency support, or currency conversion; later policy/provider code must enforce supported currencies.
- Required and preferred attributes are separate JSON maps with nonblank keys. Overlapping keys are rejected. Offer evidence maps attributes to lists of nonblank supporting excerpts or references. Missing offer evidence is valid input, not a confirmed match.
- All records forbid unexpected fields, including nested records. IDs, explanations, source values, and evidence entries must contain non-whitespace text.
- Semantic PASS requires nonempty evidence. Confidence is optional in [0, 1] and cannot replace evidence. Preference score is a percentage in [0, 100]. Scores reject booleans and non-finite values.
- Verification summaries cannot contradict supplied required checks: any FAIL means FAIL; otherwise UNKNOWN checks, missing mandatory evidence, or no checks mean UNKNOWN; otherwise PASS. Required and preferred check names must each be unique and cannot overlap. Missing preferred evidence does not belong in `missing_evidence` and does not block mandatory PASS. These consistency checks do not evaluate an offer against intent or calculate a preference score.
- DENY and REQUIRE_APPROVAL need reason codes. Reason codes are unique enums; CURRENCY_MISMATCH names the existing currency-denial requirement. Policy outcomes are recorded, not computed or authorized by the schema; the separate pure service computes them from backend authority records.
- Draft proposals can omit verification, policy decision, and digest. If supplied, verification must refer to the selected offer; policy must match its amount/currency and the proposal policy version. Offers that exceed budget or use a different currency from intent remain representable so a future verifier/policy service can explain and deny them.
- Approval and payment records require proposal/user/offer/merchant IDs, exact amount/currency, policy version, verification snapshot ID, and proposal digest. Digests must have lowercase SHA-256 hex shape (64 characters). The schemas themselves do not compute digests; the separate binding/service layer now generates and regenerates them. Hash shape does not authenticate consent.
- Record timestamps require a timezone. Approval expiry must follow creation; APPROVED/REJECTED require a decision time within that window, and PENDING cannot have a decision time. EXPIRED records can retain a historical decision time within the window. No wall-clock expiry decision is performed during record deserialization; the approval service performs explicit-time expiry and permanent INVALIDATED lifecycle transitions.
- Payment records default to CREATED with application approval PENDING. An idempotency key is required and retained exactly; no key generation or duplicate enforcement exists yet. APPROVED/REJECTED/EXPIRED application states require an approval reference; NOT_REQUIRED cannot carry one. NOT_REQUIRED applies only to application approval and never skips PayPal buyer authorization.
- PaymentState now has exactly the nine requested states, with a centralized event-driven transition table and terminal/uncertainty guards. The unused VERIFYING vocabulary from D-021 is removed by D-027. Model deserialization represents records; it does not authorize state changes or establish provider success.

## Example

```python
from app.schemas import PurchaseIntent

intent = PurchaseIntent.model_validate({
    "category": "hotel",
    "query": "Five nights with a gym and mountain view",
    "currency": "USD",
    "budget_max_minor": 150_000,
    "approval_threshold_minor": 130_000,
    "required_attributes": {"gym": True, "mountain_view": True},
    "preferred_attributes": {"private_pool": True},
})
assert PurchaseIntent.model_validate_json(intent.model_dump_json()) == intent
```

## Trust boundary

These are data records, **not trusted browser request DTOs for authorizing payment**. A schema-valid supplied status, evidence excerpt, approval ID, or digest proves only valid shape and local consistency. Backend services must reload canonical data, establish evidence provenance and ownership, recompute bindings, enforce current policy/expiry/reservations, and verify provider state before taking financial action. Pydantic deserialization does not prevent later mutation or make `model_copy(update=...)` validated; revalidate records at trust boundaries.

Run `cd backend && .venv/bin/pytest -q` for the schema suite and existing health contract test.
