# Synthetic hotel catalog

`fixtures/hotels.json` contains **eight entirely synthetic offers**. The file metadata, every offer title (`[Synthetic]`), every offer source (`synthetic_fixture:hotels:v1`), and the search response identify this data as synthetic. Names, merchant IDs, prices, cancellation terms, and amenity evidence are invented for a reproducible demonstration. No real hotel availability, booking, or PayPal merchant relationship is represented.

Prices are **integer minor-unit totals for one room over the stated number of nights**, including fictional taxes/fees. They are not nightly prices. No live dates, inventory, currency conversion, automatic stay repricing, or external search is implemented.

## Fixture cases

| Offer suffix | Currency | Total minor units | Nights | Purpose |
| --- | --- | ---: | ---: | --- |
| 001 | USD | 118000 | 5 | Gym, mountain view, free cancellation; no private pool |
| 002 | USD | 139000 | 5 | All example amenities, including private pool |
| 003 | USD | 162000 | 5 | Same amenities at a price above the example budget |
| 004 | USD | 98000 | 5 | Explicitly no gym, with evidence stating that fact |
| 005 | USD | 112000 | 5 | Cancellation attribute/evidence deliberately absent |
| 006 | EUR | 104000 | 5 | Swiss hotel with no mountain view or free cancellation |
| 007 | EUR | 99000 | 3 | Different country (France) and stay length |
| 008 | USD | 51000 | 2 | Swiss hotel with a different stay length |

Full IDs are `synthetic-hotel-001` through `synthetic-hotel-008`. Merchant IDs are stable synthetic identifiers. Evidence is keyed by the supported attribute and includes synthetic excerpts for price, currency, location, stay, and amenities. Missing cancellation evidence for offer 005 is preserved; it is not converted to true or false. No verification or policy result is precomputed.

## Search API

`POST /v1/offers/search` accepts a JSON object. `{}` browses the catalog; no natural-language parsing or policy enforcement occurs.

| Field | Meaning |
| --- | --- |
| query | Up to 200 characters; case-insensitive whitespace-separated substrings, all matched against title/city/country text |
| country | Case-insensitive exact country name; no aliases or geocoding |
| nights | Exact positive integer stay length; does not reprice offers |
| currency | Exact uppercase three-letter currency code |
| max_amount_minor | Inclusive nonnegative strict integer price ceiling; requires currency |
| attributes | Map of attribute names to strict boolean values; all must match exactly |
| offset | Nonnegative strict integer; default 0 |
| limit | Strict integer 1–100; default 20 |

All supplied filters are combined with AND. Missing attributes match neither true nor false; numeric `1` never matches boolean `true`. Query matching is textual retrieval, not semantic amenity verification. Results use stable offer-ID order, not a ranking or comparison of prices across currencies. `total` counts matches before pagination. Unknown filters and coercible numbers/booleans return HTTP 422. Caller-supplied filesystem paths are not supported.

```sh
curl --fail http://localhost:8000/v1/offers/search \
  -H 'Content-Type: application/json' \
  --data '{"country":"Switzerland","nights":5,"currency":"USD","attributes":{"gym":true,"mountain_view":true,"free_cancellation":true}}'
```

This returns offers 001, 002, and 003, with their evidence. It does **not** claim they pass verification, budget, merchant policy, approval, or payment checks. A caller may add `"max_amount_minor":150000` for an explicit retrieval ceiling, but the future policy service must independently recheck the canonical selected offer.

Responses contain `catalog_id`, `synthetic: true`, a prominent `notice`, `offers`, `total`, `offset`, and `limit`. Empty responses retain the synthetic notice. No frontend catalog UI is added in this stage; use the endpoint or `/docs`.

## Service and deployment

`app.services.catalog.CatalogService` validates the entire trusted fixture file at application startup. A missing/malformed file, schema-invalid offer, duplicate offer ID, or missing synthetic labels prevents startup; the service never silently returns a partial catalog. Search and `get_offer(offer_id)` return deep copies so callers cannot mutate canonical records. Unknown IDs return `None`.

Fixture loading is independent of the process working directory. Local code uses the repository's `fixtures/hotels.json`; the image preserves `/app/backend` and `/app/fixtures`. Backend Docker builds now use the **repository root** as their context (`docker build -f backend/Dockerfile .`). Root `.dockerignore` allows only backend runtime sources/requirements and the hotel fixture, excluding environment files, tests, dependencies, and other project content. No browser parameter can replace this trusted file. Restart the application after editing fixtures; no hot-reload or remote-write API is provided.

The catalog is retrieval only. Schema-valid evidence is not proof of a real hotel or payment permission. The [deterministic verifier](verification.md) now evaluates explicit structured requirements and preferences. The [pure financial policy service](policy.md) now evaluates financial eligibility. Proposal selection/binding and payment execution remain subsequent stages.
