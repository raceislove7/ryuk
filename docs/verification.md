# Deterministic attribute verification

Call `app.services.verifier.verify_offer(intent, offer)` with validated PurchaseIntent and canonical backend Offer records. The result is a VerificationResult containing required checks, preferred checks, evidence, missing mandatory evidence, a preference percentage, and a reproducible snapshot identifier. No API route, database persistence, UI, semantic matcher, financial policy, or payment authorization is added by this service.

```python
from app.schemas import PurchaseIntent
from app.services.catalog import CatalogService
from app.services.verifier import verify_offer

intent = PurchaseIntent(
    category="hotel",
    query="Five nights with gym, mountain view, and free cancellation",
    currency="USD",
    budget_max_minor=150_000,
    approval_threshold_minor=130_000,
    required_attributes={"gym": True, "mountain_view": True, "free_cancellation": True},
    preferred_attributes={"private_pool": True},
)
catalog = CatalogService()
assert verify_offer(intent, catalog.get_offer("synthetic-hotel-001")).status == "PASS"
assert verify_offer(intent, catalog.get_offer("synthetic-hotel-004")).status == "FAIL"
assert verify_offer(intent, catalog.get_offer("synthetic-hotel-005")).status == "UNKNOWN"
```

## Per-attribute rules

Only explicit `required_attributes` and `preferred_attributes` are compared. Supported predicates are exact equality between values of the same primitive type: boolean, integer, finite float, or nonblank string. There is no truthiness conversion, case folding, fuzzy text matching, numeric coercion, range syntax, or interpretation of evidence prose. For example, integer `1` cannot satisfy boolean `true`, integer `5` does not automatically equal float `5.0`, and `"Switzerland"` differs from `"switzerland"`. Arrays/objects, null, blank strings, missing actual values, and incompatible types yield UNKNOWN. Non-finite/non-JSON data is rejected at the service boundary.

For supported, same-type values:

| Comparison | Evidence | Result |
| --- | --- | --- |
| Values differ (including mandatory true versus actual false) | Present or absent | FAIL |
| Values match | Absent or empty | UNKNOWN |
| Values match | Nonempty per-attribute evidence | PASS |

A known structured failure takes priority over missing evidence: removing evidence cannot turn false into a match. An explicit negative requirement (`false`) can pass when the actual value is also false and evidence is present. Evidence text is copied into the check; instructions inside it are never executed or treated as authorization. Evidence presence does not establish factual authenticity or resolve contradictions in prose; canonical sourcing and any semantic interpretation require their own trust controls.

The result's mandatory status is FAIL if any required check fails; otherwise UNKNOWN if any required check is unknown or no mandatory attributes were supplied; otherwise PASS. `missing_evidence` contains required attribute names with absent/empty evidence, including failed checks lacking evidence. Preferred evidence gaps do not appear there. An absent structured fact can remain UNKNOWN even if listing prose exists, without falsely claiming that the prose itself is missing.

## Preferences

Each preference uses the same per-attribute rules and is returned in `preferred_checks`. Score is `100 × preferred PASS count / total preferences`; FAIL and UNKNOWN receive zero credit. There are no weights and no preferences yields 0.0. Preference results never affect mandatory status, and a perfect preference score cannot override FAIL or UNKNOWN. Scores are match percentages, not model confidence or payment eligibility. All checks are DETERMINISTIC and no confidence is invented.

## Scope and safety

Budget, approval threshold, currency eligibility, quantity, category, merchant policy, and provider status are **not implicitly evaluated** by this attribute-only service. Location, nights, or other supported attributes can be included explicitly in the requirement map. Free-form `query` and `notes` are not parsed. The intent parser and [pure policy service](policy.md), with later checkout services, handle their separate responsibilities; there is no hidden conversion from query text to requirements.

Consequently, hotel 003 can receive mandatory PASS while exceeding the example budget; the deterministic policy service denies that purchase when the active/requested cap is exceeded. Catalog retrieval or this verification result alone must never authorize checkout. The synthetic offers and excerpts remain fictional and do not prove real availability or booking terms.

Input models are revalidated because callers can mutate Pydantic instances. Checks are returned in sorted attribute-name order and do not mutate input records or expose their evidence lists. The service has no network calls, LLM calls, or payment dependencies.

## Snapshot identity

`verification_snapshot_id` is `verification-v1-<SHA-256 hex>`, derived from the verifier version and the complete validated intent/offer serialized as sorted-key compact JSON with non-finite numbers rejected. Identical content produces identical results regardless of map insertion order. Changed evidence, merchant, price, intent, or verifier version changes the identifier even when the final status remains the same. All relevant check evidence is included in the returned result. Increment `VERIFIER_VERSION` whenever comparison or scoring rules change.

This is an in-memory content-addressed verification record, **not** the approved proposal digest, a signature, a persisted snapshot, an audit event, or proof of current approval. Persistence, canonical proposal binding, expiry, and before-capture revalidation remain later stages.
