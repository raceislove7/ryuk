"""SQLite authority using the existing consent state machine, with no cached grants.

Each operation reloads one proposal under the same ledger write transaction as the
final reservation/claim. Provider I/O must never occur within these scopes.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app.schemas import ApprovalRequest, PolicyDecision, PolicyOutcome, PurchaseProposal
from app.services.approvals import (
    ApprovalAccessError,
    ApprovalPolicyError,
    ApprovalStateError,
    InMemoryApprovalService,
)
from app.services.checkout_store import CheckoutStore
from app.services.proposal_binding import InvalidProposalBinding, require_proposal_binding

CONSENT_FAILURES = (ApprovalPolicyError, ApprovalStateError, InvalidProposalBinding)


@contextmanager
def authority_transaction(store: CheckoutStore) -> Iterator[sqlite3.Connection]:
    """Commit observed revocation/expiry before returning an expected consent failure.

    Only for scopes where consent validation precedes any financial mutation.
    Unexpected errors still roll back the entire transaction.
    """
    failure = None
    with store.transaction() as connection:
        try:
            yield connection
        except CONSENT_FAILURES as error:
            failure = error
    if failure is not None:
        raise failure


class DurableApprovalService(InMemoryApprovalService):
    """Reuse consent rules while persisting each proposal's complete authority state."""

    def __init__(self, store: CheckoutStore) -> None:
        super().__init__()
        self.store = store

    def _load(
        self, connection: sqlite3.Connection, identifier: str, request: bool
    ) -> InMemoryApprovalService:
        if request:
            row = connection.execute(
                "SELECT proposal_id FROM approval_lookup WHERE request_id=?", (identifier,)
            ).fetchone()
            if row is None:
                raise ApprovalAccessError("Approval not found or access denied.")
            identifier = row["proposal_id"]
        engine = InMemoryApprovalService(ttl=self._ttl)
        row = connection.execute(
            "SELECT user_id,body FROM proposal_authority WHERE proposal_id=?", (identifier,)
        ).fetchone()
        if row is not None:
            data = json.loads(row["body"])
            proposal = PurchaseProposal.model_validate_json(json.dumps(data["proposal"]))
            require_proposal_binding(proposal)
            if proposal.proposal_id != identifier or row["user_id"] != proposal.user_id:
                raise ValueError("Stored proposal identity mismatch")
            engine._proposals[identifier] = proposal
            for body in data["requests"]:
                approval = ApprovalRequest.model_validate_json(json.dumps(body))
                if approval.proposal_id != identifier or approval.user_id != proposal.user_id:
                    raise ValueError("Stored approval identity mismatch")
                engine._requests[approval.approval_request_id] = approval
            current = data["current"]
            if current is not None:
                if current not in engine._requests:
                    raise ValueError("Stored current approval missing")
                engine._current[identifier] = current
            engine._last_seen[identifier] = datetime.fromisoformat(data["last_seen"])
        return engine

    def _save(
        self, connection: sqlite3.Connection, engine: InMemoryApprovalService, identifier: str
    ) -> None:
        proposal = engine._proposals.get(identifier)
        if proposal is None:
            return
        data = {
            "proposal": proposal.model_dump(mode="json"),
            "requests": [a.model_dump(mode="json") for a in engine._requests.values()],
            "current": engine._current.get(identifier),
            "last_seen": engine._last_seen[identifier].isoformat(),
        }
        old = connection.execute(
            "SELECT body FROM proposal_authority WHERE proposal_id=?", (identifier,)
        ).fetchone()
        previous = json.loads(old["body"]) if old else None
        connection.execute(
            "INSERT INTO proposal_authority VALUES (?,?,?) ON CONFLICT(proposal_id) "
            "DO UPDATE SET user_id=excluded.user_id, body=excluded.body",
            (identifier, proposal.user_id, json.dumps(data)),
        )
        connection.execute(
            "INSERT OR IGNORE INTO recovery_index(proposal_id,user_id) VALUES (?,?)",
            (identifier, proposal.user_id),
        )
        at = data["last_seen"]
        if previous is None or previous["proposal"] != data["proposal"]:
            self._audit(connection, identifier, "CANONICAL_PROPOSAL_STORED", at, {})
        old_requests = (
            {a["approval_request_id"]: a for a in previous["requests"]} if previous else {}
        )
        for approval in data["requests"]:
            key = approval["approval_request_id"]
            connection.execute(
                "INSERT OR IGNORE INTO approval_lookup VALUES (?,?)", (key, identifier)
            )
            if old_requests.get(key) != approval:
                self._audit(
                    connection,
                    identifier,
                    "APPROVAL_STATE_CHANGED",
                    at,
                    {"approval_request_id": key, "status": approval["status"]},
                )

    @staticmethod
    def _audit(
        connection: sqlite3.Connection, proposal_id: str, event: str, at: str, details: dict
    ) -> None:
        connection.execute(
            "INSERT INTO proposal_audit(proposal_id,event,at,details) VALUES (?,?,?,?)",
            (proposal_id, event, at, json.dumps(details)),
        )

    def _invoke(self, method: str, identifier: str, *, request: bool = False, **kwargs: Any) -> Any:
        failure = None
        result = None
        with self.store.transaction() as connection:
            engine = self._load(connection, identifier, request)
            proposal_id = next(iter(engine._proposals), identifier)
            try:
                result = getattr(engine, method)(identifier, **kwargs)
            except CONSENT_FAILURES as error:
                failure = error
            self._save(connection, engine, proposal_id)
        if failure is not None:
            raise failure
        return result

    def register_proposal(self, proposal: PurchaseProposal, **kwargs: Any) -> PurchaseProposal:
        with self.store.transaction() as connection:
            engine = self._load(connection, proposal.proposal_id, False)
            result = engine.register_proposal(proposal, **kwargs)
            self._save(connection, engine, proposal.proposal_id)
            return result

    def get_proposal(self, proposal_id: str, *, actor_user_id: str) -> PurchaseProposal:
        return self._invoke("get_proposal", proposal_id, actor_user_id=actor_user_id)

    def get_request(self, request_id: str, **kwargs: Any) -> ApprovalRequest:
        return self._invoke("get_request", request_id, request=True, **kwargs)

    def create_request(self, proposal_id: str, **kwargs: Any) -> ApprovalRequest:
        return self._invoke("create_request", proposal_id, **kwargs)

    def approve_request(self, request_id: str, **kwargs: Any) -> ApprovalRequest:
        return self._invoke("approve_request", request_id, request=True, **kwargs)

    def reject_request(self, request_id: str, **kwargs: Any) -> ApprovalRequest:
        return self._invoke("reject_request", request_id, request=True, **kwargs)

    def revalidate_for_checkout(self, proposal_id: str, **kwargs: Any) -> PolicyDecision:
        return self._invoke("revalidate_for_checkout", proposal_id, **kwargs)

    @contextmanager
    def checkout_guard(
        self, proposal_id: str, **kwargs: Any
    ) -> Iterator[tuple[PurchaseProposal, ApprovalRequest | None]]:
        # The database transaction, not a process-local mutex, stabilizes consent.
        with authority_transaction(self.store):
            decision = self.revalidate_for_checkout(proposal_id, **kwargs)

            if decision.decision != PolicyOutcome.ALLOW_ELIGIBLE_FOR_CHECKOUT:
                raise ApprovalPolicyError(decision)
            with self.store.transaction() as connection:
                engine = self._load(connection, proposal_id, False)
                with engine.checkout_guard(proposal_id, **kwargs) as records:
                    self._save(connection, engine, proposal_id)
                    yield records
