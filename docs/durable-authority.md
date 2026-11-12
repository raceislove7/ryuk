# Durable authority and purchase recovery

This implements the first production-readiness stage, not production certification. The runtime now uses `DurableApprovalService` with the same SQLite store instance as checkout. The in-memory service remains the consent state-machine implementation and isolated reference-test adapter.

## Records and transaction boundary

- `proposal_authority`: original/parsed intent, canonical offer/evidence, digest, review flag, all approval requests/current request and last observed workflow time, keyed per proposal and owner.
- `approval_lookup`: persistent request-to-proposal lookup.
- `proposal_audit`: canonical writes, approval status changes and the earlier workspace events; execution events stay in `checkout_audit`.
- `recovery_index`: stable owner-scoped pagination over new proposals and pre-upgrade checkout references.

Each operation reloads one proposal from SQLite and validates its Pydantic schema, identity and digest; no cached grant is authoritative. Existing consent logic preserves ownership, expiry, rejection, supersession, monotonic workflow time and permanent invalidation after observed binding/policy changes. Reading history may expire an approval and persist that transition; it never calls the provider.

The final consent check and reservation/dispatch claim share one `BEGIN IMMEDIATE` transaction. This serializes concurrent approval decisions and captures across database connections. Transactions are synchronous and reentrant only on the same store instance/thread; never await or perform provider I/O inside them. Expected consent failures commit observed expiry/revocation before returning denial; unexpected errors roll back all changes. Checkout uses that scope only with consent validation before financial mutations.

A valid, unexpired persisted application approval can survive restart. Capture still requires the current canonical digest, current policy/budget, merchant mapping, separate provider-verified buyer approval and the original exact terms. Restart never extends a consent TTL, restores a revoked grant, retries capture or replenishes funds. Known uncertain attempts reconcile through provider GET; existing duplicate/reservation/settlement protections remain.

## Recovery access

Sign in again after a backend restart: sessions are still process-local. Use **Load saved activity** to list up to 50 owner-scoped entries, then **Older activity** to page further. Inspect a saved audit without recreating a proposal. **Check existing payment** uses the existing reconciliation endpoint; it never initiates capture. The recovered view does not mount a new PayPal button or automatically create an order.

`GET /v1/history?before=<positive sequence>` is authenticated; the actor comes only from the server session. Results expose allowlisted status/amount/reference summaries, not idempotency keys or raw intent. `GET /v1/proposals/{id}/audit` includes persisted early/execution events for that owner. The browser proxy forwards history pagination, and all existing authentication/origin controls remain.

## Upgrade and legacy boundary

Finish or reconcile active transactions and take a verified private SQLite backup before rollout. Startup adds tables/indexes and backfills only existing checkout references into the recovery index; it does not overwrite accounts, holds, settlements, keys or provider references. Use a new backup destination (the command refuses overwrites):

```sh
docker compose exec -T backend python -m app.backup_checkout /app/data/ryuk.sqlite3 /app/data/pre-durable-authority.sqlite3
# Retain a protected copy outside the deployment volume for disaster recovery.
docker compose --env-file .env up -d --build --wait backend frontend
```

Pre-upgrade proposals/approvals existed only in RAM and cannot be recovered after restart. Legacy checkouts are listed and their execution audit remains inspectable; missing consent is never reconstructed from payment terms, receipts or browser input. Such records can reconcile already attempted payments, but cannot dispatch a new capture without original canonical authority. Do not start a replacement purchase merely to resolve uncertainty. Receipts/backups remain private.

These are additive compatibility changes using the existing startup schema mechanism, not the full versioned migration/PostgreSQL stage. An older application will not use durable authority and will again lose authority on restart; do not roll back source or restore an old ledger to undo provider activity.

## Remaining stages

Multi-user identity, versioned migrations/atomic provisioning, PostgreSQL deployment, retention/resource quotas, provider terminal monitoring/refund/reversal policy, full script CSP and operational recovery validation remain pending. Durability does not prove model semantic completeness or make an operator with database write access untrusted. OS ACLs, private backups and a single supported application deployment remain required. Durable intent/evidence now contain private purchase text, so storage/backup access and future retention policies must cover them.
