"""Read-only operator evidence export. No provider calls, schema changes or financial writes."""

import argparse
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.checkout import CheckoutRecord


class EvidenceUnavailable(ValueError):
    """Fixed public diagnostics without ledger contents, credentials or private paths."""


def export_acceptance(path: Path, payment_id: str | None = None) -> dict:
    """Read one consistent snapshot; emit allowlisted references/events and ledger checks."""
    if not path.is_file():
        raise EvidenceUnavailable("Configured ledger file does not exist")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        if payment_id:
            row = db.execute(
                "SELECT body FROM checkouts WHERE payment_id=?", (payment_id,)
            ).fetchone()
        else:
            row = db.execute(
                "SELECT body FROM checkouts WHERE json_extract(body,'$.payment.state')='SUCCEEDED' "
                "ORDER BY (SELECT max(sequence) FROM checkout_audit "
                "WHERE checkout_audit.payment_id=checkouts.payment_id AND event='BUDGET_SETTLED') "
                "DESC LIMIT 1"
            ).fetchone()
        if row is None:
            raise EvidenceUnavailable("No matching completed checkout was found")
        record = CheckoutRecord.model_validate_json(row["body"])
        payment = record.payment
        events = [
            dict(item)
            for item in db.execute(
                "SELECT sequence,event,at FROM checkout_audit WHERE payment_id=? ORDER BY sequence",
                (payment.payment_intent_id,),
            )
        ]
        hold = db.execute(
            "SELECT status,amount_minor,currency FROM reservations WHERE payment_id=?",
            (payment.payment_intent_id,),
        ).fetchone()
        settlements = sum(item["event"] == "BUDGET_SETTLED" for item in events)
        dispatches = sum(item["event"] == "CAPTURE_DISPATCH" for item in events)
        checks = {
            "backend_succeeded": payment.state.value == "SUCCEEDED",
            "capture_reference_recorded": bool(record.capture_id),
            "exactly_one_settlement": settlements == 1,
            "exactly_one_capture_dispatch": dispatches == 1,
            "reservation_settled_for_exact_terms": bool(
                hold
                and hold["status"] == "SETTLED"
                and hold["amount_minor"] == payment.amount_minor
                and hold["currency"] == payment.currency
            ),
        }
        return {
            "evidence_version": 1,
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "backend SQLite snapshot; not a fresh provider query or UI timing proof",
            "payment_id": payment.payment_intent_id,
            "proposal_id": payment.proposal_id,
            "order_id": record.order_id,
            "capture_id": record.capture_id,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "backend_state": payment.state.value,
            "policy_version": payment.policy_version,
            "verification_snapshot_id": payment.verification_snapshot_id,
            "checks": checks,
            "checks_passed": all(checks.values()),
            "audit": events,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=os.environ.get("RYUK_CHECKOUT_DB_PATH", ""))
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--latest-success", action="store_true")
    choice.add_argument("--payment-id")
    args = parser.parse_args()
    if not args.database:
        parser.error("Configure RYUK_CHECKOUT_DB_PATH or --database")
    try:
        evidence = export_acceptance(Path(args.database), args.payment_id)
    except (EvidenceUnavailable, sqlite3.Error, ValueError):
        parser.exit(1, "Evidence unavailable: check ledger configuration and payment reference.\n")
    print(json.dumps(evidence, indent=2))
    if not evidence["checks_passed"]:
        parser.exit(
            2, "Evidence checks incomplete; inspect this existing payment, do not retry capture.\n"
        )


if __name__ == "__main__":
    main()
