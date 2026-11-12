# Private demo operations

## Boundaries
Run one private backend worker on a protected local SQLite volume. This is not a public multi-user deployment. Sessions remain process-local; proposals/approvals and early audit persist in SQLite. See [durable authority and legacy recovery](durable-authority.md). Never infer lost authority from browser data after restart. Durable pending captures must use provider-state reconciliation, not renewed consent or an automatic capture retry. Configure HTTPS with secure cookies outside loopback.

## Back up without changing the ledger

From backend/ with the backend virtual environment active:

```sh
python -m app.backup_checkout /absolute/path/ledger.sqlite3 /private/new-backup.sqlite3
```

The command reads the source using SQLite's online backup API (including committed WAL state), writes a new private file and verifies integrity. It refuses all existing destinations, including symlinks; it never clears holds/spending. Protect backups like the live ledger. An interrupted/failed destination is not a verified backup: retain it for diagnosis and choose a new destination for a retry.

For a restore rehearsal, use an isolated host/process and a NEW destination, never the configured live path. Verify integrity and original account/hold/payment/audit counts before any traffic. Keep provider calls disabled. Before switching a real deployment to a restored ledger, stop financial writes and reconcile provider activity since that backup; a stale backup can otherwise forget captures and permit duplicates. No automatic rollback/reset/restore-in-place command is provided.

## Uncertainty and incident handling

- Save internal proposal/payment IDs and original provider request/order/capture references in private incident records; do not publish tokens or passwords.
- Query the provider using the original stored terms. Unknown provider outcomes retain their holds.
- Do not delete attempts, reset spending, release holds by age, or create a replacement purchase to resolve uncertainty.
- For an orphaned create with no stored provider ID, use the controlled merchant's Sandbox records/support and exact original reference/request ID. Do not invent a provider lookup API or silently retry a mutation.
- Rotate the private demo password and restart to invalidate process-local sessions if compromise is suspected; preserve the ledger. Capture reconciliation remains tied to durable original terms.
- Use trusted edge request limits for public-facing infrastructure; do not accept arbitrary forwarded IP headers as identity.

## Container rehearsal performed

A separately named Docker Compose project built both images using the managed public CA build secret. Credentials and demo enablement were explicitly disabled, separate ports/volume were used, both health checks passed, frontend returned HTTP 200 and backend /health returned ok. No private ledger, buyer interaction or provider capture was used. This verifies packaging/default fail-closed startup, not a full payment deployment.

## Mock rehearsal

Start the backend fixture from backend/:

```sh
RYUK_E2E_TEST_ONLY=1 PYTHONPATH=. python tests/frontend_server.py
```

It always creates a fresh temporary ledger; its reset endpoints are not in production app/image startup. In frontend/, build and start the standalone production server in another terminal:

```sh
npm run build
mkdir -p .next/standalone/.next/static
cp -r .next/static/. .next/standalone/.next/static/
RYUK_BACKEND_URL=http://127.0.0.1:8100 HOSTNAME=127.0.0.1 PORT=3100 node .next/standalone/server.js
```

Then run `npm run test:e2e` in frontend/. If using an installed system Chromium, set `CHROMIUM_PATH=/usr/bin/chromium` for that command; otherwise install Playwright's matching Chromium. The default test frontend URL is http://localhost:3100 and backend is http://127.0.0.1:8100. Do not substitute your live demo URLs. Model/provider behavior is mocked. Stop these fixture processes after testing; do not use them for user purchases.

## Read-only payment acceptance receipt
After updating/rebuilding the backend, run from the project directory:

```sh
docker compose exec -T backend python -m app.export_acceptance --latest-success > ryuk-payment-evidence.json
```

For a specific Ryuk internal payment reference, replace `--latest-success` with `--payment-id <reference>`. The command reads a consistent SQLite snapshot with query_only enabled; it never creates a missing database, calls PayPal, captures/retries a payment or resets records. It exports only allowlisted identifiers, amount/currency, recorded backend state, snapshot/policy references and audit event names/times. It omits actor identity, request text, idempotency keys, audit details, credentials and session data.

`checks_passed: true` means the stored backend record is SUCCEEDED, has a capture reference, exactly one capture-dispatch event, exactly one settlement event, and one SETTLED reservation matching the exact amount/currency. A failed check exits with status 2; investigate that existing payment instead of paying again. No match/configuration error exits with status 1. A receipt is a snapshot of backend evidence, not a fresh provider query or proof of UI timing. Compare its capture reference with the seller's Sandbox Activity for independent provider evidence.

Keep the receipt private; its default filename pattern is Git-ignored. Redirection creates a local receipt file, so protect it with your OS account/file permissions. Never commit private transaction receipts or upload .env. For UI acceptance, also keep a screenshot of Ryuk's Payment confirmed result. Standalone test receipts do not prove that a different transaction passed through the website.

## Held capture investigation
Use the local [operator recovery command](operator-recovery.md) to list held attempts without writes, then explicitly reconcile one through provider GET and the existing atomic coordinator. Never release an ambiguous hold by TTL or repeat capture.
