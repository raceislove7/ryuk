# Held capture recovery (Sandbox operator)

Local filesystem access to the backend container/ledger is the operator boundary. There is no public force-release endpoint. This command never creates an order, retries capture, refunds, deletes financial records or releases a hold by age.

## Inspect first — read-only, no provider calls

```sh
docker compose exec -T backend python -m app.recover_checkout
```

This lists up to 100 held checkout summaries (ID, state, exact money and retained decline code). For the next page, pass `--after <last-payment-id>`; for one record pass `--payment-id <internal-payment-id>`. Missing files are never created. Keep output private.

## Reconcile an existing attempt

After checking the existing record, explicitly request authenticated provider GET and coordinator reconciliation:

```sh
docker compose exec -T backend python -m app.recover_checkout \
  --payment-id <internal-payment-id> --apply \
  --operator <operator-label> --reason "Investigating retained capture reservation"
```

The actor is loaded from the stored checkout, not a user-supplied identity. The operator label/reason and result are audited; do not put credentials or private buyer details in those labels. Backend Sandbox credentials stay in the backend environment. Exit 0 means terminal resolved state, exit 2 means uncertainty/hold retained, exit 1 means unavailable/invalid configuration or operation. A successful command can settle a verified payment as well as release a verified failure; inspect its state instead of assuming release.

## Evidence required for release

Existing verified terminal failed capture/void observations still release through the normal atomic state machine. Additionally, a capture HTTP 422 with name UNPROCESSABLE_ENTITY and exactly one issue INSTRUMENT_DECLINED is recognized as a definitive rejection of that dispatched instrument. Only the code and matching order/request dispatch binding are retained; raw provider error bodies are never saved/reflected. The coordinator then GETs the same order and validates exact reference/merchant/amount/currency. Release is allowed only with no capture present and a recognized open-order state, or an independently verified terminal failure. A completed capture settles; a pending/refunded/malformed/mismatched response or unavailable GET retains the hold. No blind POST retry occurs.

If the GET was temporarily unavailable, the decline evidence survives restart for later operator or existing UI reconciliation. Repeated/concurrent reconciliation cannot release or settle twice. The local failed checkout is terminal and cannot be recaptured through Ryuk, even if PayPal still shows its order open. External seller operations after local termination require the separate terminal-monitoring work; this does not void a PayPal order or monitor later external captures/refunds/reversals.

Other HTTP 4xx/5xx, unknown/multi-issue error bodies, timeout, invalid JSON, ORDER_ALREADY_CAPTURED and open-order status without matching saved decline evidence remain uncertain. In particular, pre-upgrade error bodies were not retained: an operator cannot safely recreate that evidence merely from a remembered decline, age, browser callback or receipt. Use original references and merchant records/provider support to establish financial truth. The command intentionally has no force-release flag for an unresolved historical hold.

Before upgrading, finish/reconcile active payments and take a verified private ledger backup. New evidence fields are optional in existing record JSON; accounts, reservations, operation keys and settlements are preserved. No new database tables or reset is required for this change.
