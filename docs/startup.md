# Start and present the private Sandbox release

## Existing installation

Before updating, finish/reconcile active purchases. Restarting invalidates sessions; new canonical proposals/approvals, checkout records and holds persist. Pre-upgrade in-memory consent cannot be recovered; see [upgrade and legacy recovery](durable-authority.md). Preserve any local edits and private configuration. Inspect first:

```sh
git status --short
git fetch origin --tags
git show --no-patch v0.1.1-sandbox-demo
```

If there are edits, save/review them before switching; do not overwrite or blindly reapply them. From a clean checkout, use the tested tag (detached HEAD is expected):

```sh
git switch --detach v0.1.1-sandbox-demo
docker compose --env-file .env up -d --build --wait backend frontend ingress
git describe --tags --exact-match
docker compose ps
curl --fail http://localhost:8000/health
curl --fail --output /dev/null http://localhost:3000
```

Health checks establish process/HTTP availability, not provider readiness or a successful payment. A checked-out tag alone does not identify an older container; rebuild before presenting. No signed/reproducible container digest or deployment attestation is supplied with this source tag.

## New installation

Requires Git, Docker Engine with BuildKit and Compose v2. Follow the clean-checkout tag selection above, then create `.env` only if absent:

```sh
cp -n .env.example .env
```

Edit the private file locally. Never send credentials in chat or commit them. Required settings for the Groq/PayPal demo:

| Setting | Local value / source |
| --- | --- |
| LLM_PROVIDER | groq |
| GROQ_API_KEY | Your private Groq key |
| GROQ_MODEL | openai/gpt-oss-120b (validated example; availability depends on your Groq account) |
| PAYPAL_ENV | sandbox |
| PAYPAL_BASE_URL | https://api-m.sandbox.paypal.com |
| PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET | Same Sandbox REST app, backend only |
| PAYPAL_MERCHANT_ID | Business seller's merchant/payer ID for that app; not its client ID |
| RYUK_DEMO_ENABLED | true |
| RYUK_DEMO_PASSWORD | Unique private password, at least 16 characters |
| RYUK_APP_ORIGIN | http://localhost:3000 |
| RYUK_SECURE_COOKIES | false only for this local HTTP setup; true with HTTPS |

OpenAI remains supported via LLM_PROVIDER=openai plus OPENAI_API_KEY and OPENAI_MODEL. Do not configure secrets as NEXT_PUBLIC variables. Compose supplies the internal backend URL and persistent database path. Use a separate Sandbox **personal buyer** account in the PayPal window; the app belongs to the **business seller**. Both are test accounts, not your real PayPal login.

Build/start with the Compose command above and open exactly `http://localhost:3000`. Unlock using the demo password. A different hostname/port needs matching origin configuration. Loopback publishing is intentional; do not expose this demo publicly.

## Presentation and evidence

Follow the [three-minute walkthrough](demo-script.md). With existing spending, use prior labeled payment evidence rather than trying the original expensive examples again. Export the existing successful payment without a provider call:

```sh
docker compose exec -T backend python -m app.export_acceptance --latest-success > ryuk-payment-evidence.json
```

Check the exit status immediately (`echo $?` in Bash/WSL). Zero and checks_passed=true mean the exported record passes local receipt checks. Status 1 means unavailable/configuration/reference error; status 2 means incomplete evidence. Neither calls for a new purchase. Keep the receipt and a success screenshot private. [Operations](operations.md) explains backup/recovery and provider comparison.

To stop, use `docker compose stop`; to resume the same deployment, use `docker compose start`. Never use `down -v`, delete the ledger or release holds merely to replenish a demo budget. A new process still invalidates sessions; persisted approvals keep their original expiry and must pass current policy. Inspect existing uncertain payments before restarting financial activity.

## Automated checks

Use Python 3.12, Node 22+, the pinned dependencies and separate terminals. These checks use mocks and fresh fixture ledgers, not live PayPal:

```sh
# backend/ with its development virtual environment active
ruff check .
python -m pip check
pytest -q

# frontend/
npm run lint
npm run typecheck
npm run build
```

For the isolated production browser rehearsal, see [operations](operations.md). Never point tests/e2e.mjs at your live demo deployment: its reset actions are intended only for the guarded fresh-ledger fixture. The source release carries test results, not a claim that all production security gaps are closed.

## Proxy-aware login configuration
Compose now includes a trusted ingress and requires a private RYUK_PROXY_SHARED_SECRET (32–256 random ASCII characters) for browser login. Add it locally to .env before upgrading; recreate backend, frontend and ingress together. Frontend port 3000 is not directly published. See [login rate-limit trust boundary](login-rate-limits.md).
