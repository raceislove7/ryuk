"""Durable single-host checkout ledger; trusted backend configuration only.

SQLite transactions span authorization/reservation claims, never provider I/O.
Use a local persistent file, not NFS or an ephemeral container filesystem.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from threading import local

from pydantic import TypeAdapter

from app.schemas.checkout import CheckoutRecord
from app.schemas.domain import MinorUnits, NonEmptyString
from app.schemas.policy import BudgetSnapshot, FinancialPolicy
from app.services.paypal import Identifier

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recovery_index (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS recovery_owner ON recovery_index(user_id,sequence);
CREATE TABLE IF NOT EXISTS proposal_authority (
 proposal_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS proposal_owner ON proposal_authority(user_id);
CREATE TABLE IF NOT EXISTS approval_lookup (
 request_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL REFERENCES proposal_authority(proposal_id)
);
CREATE TABLE IF NOT EXISTS proposal_audit (
 sequence INTEGER PRIMARY KEY, proposal_id TEXT NOT NULL REFERENCES proposal_authority(proposal_id),
 event TEXT NOT NULL, at TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
 user_id TEXT PRIMARY KEY, currency TEXT NOT NULL,
 limit_minor INTEGER NOT NULL CHECK(limit_minor >= 0),
 settled_minor INTEGER NOT NULL CHECK(settled_minor >= 0)
);
CREATE TABLE IF NOT EXISTS policies (user_id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS merchants (merchant_id TEXT PRIMARY KEY, paypal_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkouts (
 payment_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE,
 user_id TEXT NOT NULL, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
 payment_id TEXT PRIMARY KEY REFERENCES checkouts(payment_id),
 user_id TEXT NOT NULL REFERENCES accounts(user_id), currency TEXT NOT NULL,
 amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
 status TEXT NOT NULL CHECK(status IN ('HELD', 'SETTLED', 'RELEASED'))
);
CREATE TABLE IF NOT EXISTS checkout_audit (
 sequence INTEGER PRIMARY KEY, payment_id TEXT NOT NULL REFERENCES checkouts(payment_id),
 event TEXT NOT NULL, at TEXT NOT NULL, details TEXT NOT NULL
);
INSERT OR IGNORE INTO recovery_index(proposal_id,user_id)
 SELECT proposal_id,user_id FROM checkouts ORDER BY rowid;
"""


class CheckoutAccessError(PermissionError):
    """Missing record or wrong authenticated owner."""


class CheckoutStore:
    def __init__(self, path: str | Path) -> None:
        if str(path) == ":memory:":
            raise ValueError("Checkout requires a persistent SQLite file")
        self.path = Path(path).resolve()
        self._transaction_state = local()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(_SCHEMA)
        self.path.chmod(0o600)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Serialize claims across connections/processes; exceptions roll back everything."""
        active = getattr(self._transaction_state, "connection", None)
        if active is not None:
            # Synchronous composition only: never await inside any ledger transaction.
            yield active
            return
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._transaction_state.connection = connection
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            self._transaction_state.connection = None
            connection.close()

    def create_account(self, budget: BudgetSnapshot) -> None:
        budget = BudgetSnapshot.model_validate(budget.model_dump())
        if budget.reserved_minor:
            raise ValueError("Reservations must be created by checkout, not imported")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?)",
                (
                    budget.user_id,
                    budget.currency,
                    budget.limit_minor,
                    budget.settled_minor,
                ),
            )

    def set_budget_limit(self, user_id: str, limit_minor: int) -> None:
        limit = TypeAdapter(MinorUnits).validate_python(limit_minor)
        with self.transaction() as connection:
            if (
                connection.execute(
                    "UPDATE accounts SET limit_minor=? WHERE user_id=?", (limit, user_id)
                ).rowcount
                != 1
            ):
                raise CheckoutAccessError("Budget account not found")

    def put_policy(self, policy: FinancialPolicy) -> None:
        policy = FinancialPolicy.model_validate(policy.model_dump())
        with self.transaction() as connection:
            budget = self.budget(connection, policy.user_id)
            if budget.currency != policy.currency:
                raise ValueError("Policy and account currencies differ")
            connection.execute(
                "INSERT INTO policies VALUES (?, ?) ON CONFLICT(user_id) "
                "DO UPDATE SET body=excluded.body",
                (policy.user_id, policy.model_dump_json()),
            )

    def map_merchant(self, merchant_id: str, paypal_merchant_id: str) -> None:
        merchant = TypeAdapter(NonEmptyString).validate_python(merchant_id)
        paypal_id = TypeAdapter(Identifier).validate_python(paypal_merchant_id)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO merchants VALUES (?, ?) ON CONFLICT(merchant_id) "
                "DO UPDATE SET paypal_id=excluded.paypal_id",
                (merchant, paypal_id),
            )

    def policy(self, connection: sqlite3.Connection, user_id: str) -> FinancialPolicy:
        row = connection.execute("SELECT body FROM policies WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            raise CheckoutAccessError("Current backend policy not configured")
        return FinancialPolicy.model_validate_json(row["body"])

    def budget(self, connection: sqlite3.Connection, user_id: str) -> BudgetSnapshot:
        row = connection.execute("SELECT * FROM accounts WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            raise CheckoutAccessError("Budget account not configured")
        held = connection.execute(
            "SELECT COALESCE(SUM(amount_minor), 0) FROM reservations "
            "WHERE user_id=? AND status='HELD'",
            (user_id,),
        ).fetchone()[0]
        return BudgetSnapshot(
            user_id=user_id,
            currency=row["currency"],
            limit_minor=row["limit_minor"],
            settled_minor=row["settled_minor"],
            reserved_minor=held,
        )

    def merchant(self, connection: sqlite3.Connection, merchant_id: str) -> str:
        row = connection.execute(
            "SELECT paypal_id FROM merchants WHERE merchant_id=?", (merchant_id,)
        ).fetchone()
        if row is None:
            raise CheckoutAccessError("Supported Sandbox merchant mapping not configured")
        return row["paypal_id"]

    def load(self, connection: sqlite3.Connection, payment_id: str, actor: str) -> CheckoutRecord:
        row = connection.execute(
            "SELECT user_id, body FROM checkouts WHERE payment_id=?", (payment_id,)
        ).fetchone()
        if row is None or row["user_id"] != actor:
            raise CheckoutAccessError("Checkout not found or access denied")
        record = CheckoutRecord.model_validate_json(row["body"])
        if record.payment.user_id != actor or record.payment.payment_intent_id != payment_id:
            raise CheckoutAccessError("Checkout identity mismatch")
        return record

    def save(self, connection: sqlite3.Connection, record: CheckoutRecord) -> None:
        record = CheckoutRecord.model_validate(record.model_dump())
        connection.execute(
            "UPDATE checkouts SET body=? WHERE payment_id=?",
            (record.model_dump_json(), record.payment.payment_intent_id),
        )

    def audit(
        self,
        connection: sqlite3.Connection,
        payment_id: str,
        event: str,
        at: datetime,
        details: dict | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO checkout_audit(payment_id,event,at,details) VALUES (?,?,?,?)",
            (payment_id, event, at.isoformat(), json.dumps(details or {})),
        )

    def get_checkout(self, payment_id: str, *, actor_user_id: str) -> CheckoutRecord:
        with self.transaction() as connection:
            return self.load(connection, payment_id, actor_user_id)

    def get_budget(self, user_id: str) -> BudgetSnapshot:
        """Backend ledger access, never accept an actor supplied by browser JSON."""
        with self.transaction() as connection:
            return self.budget(connection, user_id)

    def get_audit(self, payment_id: str, *, actor_user_id: str) -> list[dict]:
        with self.transaction() as connection:
            self.load(connection, payment_id, actor_user_id)
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT sequence,event,at,details FROM checkout_audit WHERE payment_id=? "
                    "ORDER BY sequence",
                    (payment_id,),
                )
            ]
