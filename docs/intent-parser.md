# Intent parser

`IntentParser` is an async interface: `await parser.parse(query) -> PurchaseIntent`. `OpenAIIntentParser` uses the OpenAI Responses API with strict structured output; `FakeIntentParser` is an exact-query lookup for deterministic tests. Neither implementation changes active financial policy, approves purchases, or exposes payment tools.

## Structured extraction and domain validation

The provider returns `LLMIntentExtraction`, a closed Pydantic schema with every field required, nullable values for ambiguity, and separate required/preferred attribute lists. Lists of named, quoted scalar attributes avoid open dictionaries in the provider's strict JSON schema. The backend converts those lists to PurchaseIntent maps only after validation. Raw JSON blobs, unexpected fields, arbitrary payment/status commands, duplicate keys, role collisions, and nonconforming types are rejected.

The original query is preserved by the backend; the provider cannot rewrite it. Attribute quotes must be exact, uniquely occurring substrings of the query. Explicit mandatory/preferred wording in those quotes is checked against the chosen list. Category labels are trimmed and case-normalized. Hotel room counts must agree with quantity; a multiroom hotel request needs an explicit mandatory `rooms` requirement so quantity cannot silently become the number of nights. An unspecified quantity defaults to one unless the quoted rooms requirement provides it. Location and stay requirements use canonical keys compatible with the catalog/verifier.

Step 12 also checks explicit role wording in the enclosing source clause so a model
cannot evade it with a shortened quote. This still does not prove completeness:
every model-derived workspace proposal now requires bound buyer review of the
original instruction versus parsed requirements before checkout (D-033).

These checks catch inconsistent structured output; they do not prove that the model captured every nuance or requirement. Natural-language extraction remains untrusted and needs live evaluation and later user review/current-policy checks. Tests using gold responses do not measure live model accuracy.

## Financial input rules

- A finite, explicit total budget is mandatory. No missing, null, unlimited, or model-invented budget is converted to an unlimited/high sentinel value.
- A budget mention carries the written amount and an exact source quote containing budget/ceiling wording and explicit currency. The backend checks the quote and requires exactly the stated numeric amount, preventing invented amounts or substituting an approval threshold for a budget.
- Supported currencies are USD, EUR, CHF, GBP (two minor-unit decimal places), and JPY (zero). Supported explicit names include US dollars, euros, Swiss francs, British pounds/pounds sterling, and Japanese yen; the euro symbol is accepted. Bare `$` or `¥` is ambiguous without explicit currency information. Mixed supported currencies require clarification; no exchange conversion is implemented.
- Written amounts use comma thousands separators and dot decimals. Decimal arithmetic, with sufficient precision for the source amount, converts to integer minor units. Fractional minor units, negative values, ambiguous formats, and per-unit rates in the budget quote require clarification rather than rounding or repricing. An explicit zero remains zero.
- An explicit approval threshold must have quoted ask/approval/confirmation wording, use the same currency, and not exceed budget. If no threshold is specified, the application threshold defaults conservatively to **zero**, requiring later application approval for any positive amount. That default does not grant consent or skip PayPal buyer authorization. Ambiguous threshold wording should produce NEEDS_CLARIFICATION.
- These are proposed purchase limits, not writes to active policy, remaining budget, merchant allowances, or approvals. The [deterministic policy service](policy.md) is authoritative for eligibility and independently applies active limits; transactional checkout controls remain later work.

## Endpoint and errors

`POST /v1/agent/parse` accepts `{"query":"..."}` with nonblank text up to 4000 characters. It returns PurchaseIntent. It now requires the configured opaque private session and exact mutation Origin before initializing a billable provider. Unsigned Bearer/user-ID headers do not authenticate; unconfigured auth returns 503, missing/invalid session 401, and wrong Origin 403. A missing provider configuration does not prevent API startup, health checks, or catalog search.

```sh
curl --fail http://localhost:8000/v1/agent/parse \
  --cookie private-session.cookies \
  -H 'Origin: http://localhost:3000' \
  -H 'Content-Type: application/json' \
  --data '{"query":"Find a hotel in Switzerland for 5 nights. Budget USD 1,500. Gym mandatory. Mountain view required. Free cancellation required. Private pool preferred. Ask me above USD 1,300."}'
```

The cookie file in this illustrative command must come from an authenticated private
session; protect it as a credential. The browser normally uses the workspace proxy.

| Outcome | HTTP | Error code |
| --- | --- | --- |
| Clarification needed / no safely extractable finite intent | 422 | INTENT_CLARIFICATION_REQUIRED |
| Invalid request shape, blank/oversized query, unexpected request fields | 422 | Fixed input-free validation message |
| Invalid, incomplete, or refused provider output | 502 | INVALID_PARSER_OUTPUT |
| Missing API key/model, provider error, rate limit, or timeout | 503 | PARSER_UNAVAILABLE |

The production dependency uses an explicitly configured model, a 20-second timeout, zero automatic retries, no tools, and `store=false`. It closes clients after each request. Model/provider errors return fixed safe messages rather than raw payloads, keys, or provider exception details. Model-supplied clarification text is not echoed to the caller. A fabricated result or test fake is never used as a fallback.

## Configuration

For Compose, copy `.env.example` to ignored `.env`, set `OPENAI_API_KEY` and a structured-output-capable `OPENAI_MODEL`, and run `docker compose up --build -d --wait backend`. Values are passed only to the backend at runtime; never put them in NEXT_PUBLIC variables, source, fixtures, or build arguments. Empty values leave `/v1/agent/parse` unavailable (503), with the catalog and health working.

For local development, set the same two variables in the backend process environment using your terminal/secret manager before starting Uvicorn. Local Uvicorn does not automatically load the repository's `.env` in this setup. The model is not chosen silently. Additional currencies/providers can be added behind the interface after defining and testing their conversion/validation behavior.

In a managed environment with a TLS-inspecting proxy, dependency installation already supports the optional public CA build mount documented in README.md. A live HTTPS call from a running container may also need that public CA bundle mounted read-only and `SSL_CERT_FILE` set to the mounted bundle path in an environment-specific Compose override. Do not copy session certificates into images or disable TLS verification. This override is unrelated to API credentials and stays outside the repository.

## Deterministic testing and current evidence

`fixtures/intent_prompts.json` contains 15 synthetic prompt cases with hand-authored structured responses and expected intents/clarification outcomes. Cases cover the hotel demo, required/preferred separation, currencies, exact decimals, zero budgets, negative requirements, rooms versus nights, missing/unlimited budgets, ambiguous thresholds/currencies, and fractional minor units.

`FakeIntentParser` receives an explicit prompt-to-extraction mapping, deep-copies its fixtures, and uses the same Pydantic/source/monetary validation path as production. Unknown prompts require clarification; it is not a regex substitute for an LLM and is never selected by production configuration. Both implementations run the 15 gold cases: the real SDK path uses a mock HTTP transport, validating the actual outgoing strict schema and the SDK's response decoding. Additional tests exercise output tampering, role changes, provider timeouts/rate limits/refusals, safe error handling, and production dependency wiring.

No paid/live model call has been performed. Provider-backed code is implemented and mock-integrated; live semantic quality and deployment credentials/model readiness remain unverified. No frontend parser UI, approval workflow, or payment behavior is implemented by the parser. The separate deterministic policy service now evaluates financial eligibility.

## Groq HTTP 400 compatibility repair
Set LLM_PROVIDER=groq, the private GROQ_API_KEY and GROQ_MODEL=openai/gpt-oss-120b in the backend environment. Groq rejects overlapping integer/number anyOf alternatives; the transport compiler removes only the redundant integer branch, since number includes integers. Shared strict application validation and original/parsed-intent approval remain unchanged. The synthetic gold request was live-validated with this model; this is not general semantic or payment acceptance. Do not switch models to work around the old schema error. Pull the fix and rebuild/recreate the backend. New safe error messages distinguish HTTP authentication, access, model availability, rate/quota and request/schema rejection without raw provider details.
