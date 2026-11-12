"""Local operator recovery: inspect holds, or GET-only reconcile one existing capture.

No force release, capture retry, new checkout, refund or browser operator endpoint.
"""

import argparse
import asyncio
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.checkout import CheckoutRecord
from app.services.checkout import CheckoutService
from app.services.checkout_store import CheckoutStore
from app.services.durable_approvals import DurableApprovalService
from app.services.paypal import PayPalSandboxAdapter, PayPalSettings


def inspect_holds(path: Path, payment_id: str | None = None, after: str = "") -> list[dict]:
    """Read a bounded consistent snapshot without creating a missing database."""
    if not path.is_file():
        raise ValueError("Existing ledger required")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        rows = connection.execute(
            "SELECT c.body FROM checkouts c JOIN reservations r ON r.payment_id=c.payment_id "
            "WHERE r.status='HELD' AND (? IS NULL OR c.payment_id=?) "
            "AND c.payment_id>? ORDER BY c.payment_id LIMIT 100",
            (payment_id, payment_id, after),
        ).fetchall()
        result = []
        for row in rows:
            record = CheckoutRecord.model_validate_json(row[0])
            result.append(
                {
                    "payment_id": record.payment.payment_intent_id,
                    "state": record.payment.state,
                    "amount_minor": record.payment.amount_minor,
                    "currency": record.payment.currency,
                    "decline_evidence": record.capture_decline_code,
                }
            )
        return result


async def recover_checkout(
    path: Path, payment_id: str, paypal: PayPalSandboxAdapter, *, operator: str, reason: str
) -> dict:
    """Provider GET may settle/release only through the existing atomic coordinator."""
    if not path.is_file() or not all(0 < len(s.strip()) <= 200 for s in (operator, reason)):
        raise ValueError("Existing ledger and bounded operator/reason labels required")
    store = CheckoutStore(path)
    with store.transaction() as connection:
        row = connection.execute(
            "SELECT user_id FROM checkouts WHERE payment_id=?", (payment_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Checkout unavailable")
        actor = row["user_id"]  # Local operator owns filesystem access, never browser identity.
        store.audit(
            connection,
            payment_id,
            "OPERATOR_RECONCILIATION_REQUESTED",
            datetime.now(timezone.utc),
            {"operator": operator, "reason": reason},
        )
    service = CheckoutService(store, DurableApprovalService(store), paypal)
    record = await service.reconcile(payment_id, actor_user_id=actor)
    with store.transaction() as connection:
        store.audit(
            connection,
            payment_id,
            "OPERATOR_RECONCILIATION_FINISHED",
            datetime.now(timezone.utc),
            {"state": record.payment.state},
        )
    return {
        "payment_id": payment_id,
        "state": record.payment.state,
        "resolved": record.payment.state in {"SUCCEEDED", "FAILED"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("RYUK_CHECKOUT_DB_PATH", ""))
    parser.add_argument("--payment-id")
    parser.add_argument(
        "--after", default="", help="List holds after this payment ID (100 per page)"
    )
    parser.add_argument("--apply", action="store_true", help="GET-only provider reconciliation")
    parser.add_argument("--operator")
    parser.add_argument("--reason")
    args = parser.parse_args()
    if not args.database:
        parser.error("Configure a ledger path")
    if args.apply and not (args.payment_id and args.operator and args.reason):
        parser.error("--apply requires --payment-id, --operator and --reason")
    try:
        if not args.apply:
            print(json.dumps(inspect_holds(Path(args.database), args.payment_id, args.after)))
            return

        async def run() -> dict:
            async with PayPalSandboxAdapter(PayPalSettings.from_env()) as paypal:
                return await recover_checkout(
                    Path(args.database),
                    args.payment_id,
                    paypal,
                    operator=args.operator,
                    reason=args.reason,
                )

        result = asyncio.run(run())
        print(json.dumps(result))
    except Exception:
        parser.exit(1, "Recovery unavailable; preserve hold and inspect the existing checkout.\n")
    if not result["resolved"]:
        parser.exit(2, "Outcome remains uncertain; reservation retained. Do not retry capture.\n")


if __name__ == "__main__":
    main()
