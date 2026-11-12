"""Thin frontend orchestration over existing catalog, verifier, policy and approvals."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import ApprovalRequest, PurchaseIntent, PurchaseProposal
from app.schemas.catalog import CatalogSearchRequest
from app.schemas.policy import AttemptSnapshot
from app.services.approvals import ApprovalAccessError, InMemoryApprovalService
from app.services.catalog import CatalogService
from app.services.checkout_store import CheckoutStore
from app.services.durable_approvals import authority_transaction
from app.services.verifier import verify_offer


class WorkspaceService:
    def __init__(
        self, catalog: CatalogService, store: CheckoutStore, approvals: InMemoryApprovalService
    ) -> None:
        self.catalog, self.store, self.approvals = catalog, store, approvals

    def event(self, proposal_id: str, event: str, details: dict | None = None) -> None:
        with authority_transaction(self.store) as connection:
            connection.execute(
                "INSERT INTO proposal_audit(proposal_id,event,at,details) VALUES (?,?,?,?)",
                (
                    proposal_id,
                    event,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(details or {}),
                ),
            )

    def _inputs(self, connection, proposal: PurchaseProposal) -> dict:
        return {
            "policy": self.store.policy(connection, proposal.user_id),
            "budget": self.store.budget(connection, proposal.user_id),
            "attempts": AttemptSnapshot(
                user_id=proposal.user_id, proposal_id=proposal.proposal_id, state="CLEAR"
            ),
        }

    def describe(self, proposal_id: str, actor: str) -> dict:
        proposal = self.approvals.get_proposal(proposal_id, actor_user_id=actor)
        with authority_transaction(self.store) as connection:
            inputs = self._inputs(connection, proposal)
            existing = connection.execute(
                "SELECT payment_id FROM checkouts WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if existing is not None:
                inputs["attempts"] = AttemptSnapshot(
                    user_id=actor, proposal_id=proposal_id, state="DUPLICATE"
                )
            decision = self.approvals.revalidate_for_checkout(
                proposal_id,
                actor_user_id=actor,
                at=datetime.now(timezone.utc),
                **inputs,
            )
        return {
            "proposal": proposal.model_dump(mode="json"),
            "policy": decision.model_dump(mode="json"),
            "required_verified": sum(
                c.status == "PASS" and bool(c.evidence)
                for c in proposal.verification.required_checks
            ),
            "required_total": len(proposal.verification.required_checks),
        }

    def investigate(self, intent: PurchaseIntent, actor: str) -> dict:
        # Preserve unsafe candidates: retrieval must not hide policy-denied examples.
        search = self.catalog.search(CatalogSearchRequest(currency=intent.currency, limit=8))
        candidates = []
        request_id = str(uuid4())
        with authority_transaction(self.store) as connection:
            policy = self.store.policy(connection, actor)
        for offer in search.offers:
            proposal = self.approvals.register_proposal(
                PurchaseProposal(
                    proposal_id=str(uuid4()),
                    user_id=actor,
                    intent=intent,
                    offer=offer,
                    policy_version=policy.version,
                    created_at=datetime.now(timezone.utc),
                    verification=verify_offer(intent, offer),
                    intent_review_required=True,
                ),
                at=datetime.now(timezone.utc),
            )
            for name, details in [
                ("USER_INTENT_CREATED", {"request_id": request_id}),
                ("OFFERS_FOUND", {"count": search.total}),
                (
                    "VERIFICATION_COMPLETED",
                    {"snapshot": proposal.verification.verification_snapshot_id},
                ),
            ]:
                self.event(proposal.proposal_id, name, details)
            candidate = self.describe(proposal.proposal_id, actor)
            self.event(
                proposal.proposal_id,
                "POLICY_EVALUATED",
                {
                    "decision": candidate["policy"]["decision"],
                    "reason_codes": candidate["policy"]["reason_codes"],
                },
            )
            candidates.append(candidate)
        return {
            "request_id": request_id,
            "intent": intent.model_dump(mode="json"),
            "candidates": candidates,
            "synthetic": True,
            "notice": search.notice,
        }

    def request_approval(self, proposal_id: str, actor: str) -> ApprovalRequest:
        proposal = self.approvals.get_proposal(proposal_id, actor_user_id=actor)
        with authority_transaction(self.store) as connection:
            approval = self.approvals.create_request(
                proposal_id,
                actor_user_id=actor,
                at=datetime.now(timezone.utc),
                **self._inputs(connection, proposal),
            )
        self.event(
            proposal_id, "APPROVAL_REQUESTED", {"approval_request_id": approval.approval_request_id}
        )
        return approval

    def decide(self, request_id: str, actor: str, decision: str) -> ApprovalRequest:
        now = datetime.now(timezone.utc)
        request = self.approvals.get_request(request_id, actor_user_id=actor, at=now)
        if decision == "REJECT":
            result = self.approvals.reject_request(request_id, actor_user_id=actor, at=now)
        else:
            proposal = self.approvals.get_proposal(request.proposal_id, actor_user_id=actor)
            with authority_transaction(self.store) as connection:
                inputs = self._inputs(connection, proposal)
                existing = connection.execute(
                    "SELECT 1 FROM checkouts WHERE proposal_id=?", (proposal.proposal_id,)
                ).fetchone()
                if existing:
                    inputs["attempts"] = AttemptSnapshot(
                        user_id=actor, proposal_id=proposal.proposal_id, state="DUPLICATE"
                    )
                result = self.approvals.approve_request(
                    request_id, actor_user_id=actor, at=now, **inputs
                )
        self.event(
            request.proposal_id,
            "APPROVAL_GRANTED" if decision == "APPROVE" else "APPROVAL_REJECTED",
            {"approval_request_id": request_id},
        )
        return result

    def timeline(self, proposal_id: str, actor: str) -> list[dict]:
        try:
            self.approvals.get_proposal(proposal_id, actor_user_id=actor)
        except ApprovalAccessError:
            # Pre-upgrade checkouts remain inspectable, but never regain lost consent.
            with self.store.transaction() as connection:
                row = connection.execute(
                    "SELECT payment_id FROM checkouts WHERE proposal_id=? AND user_id=?",
                    (proposal_id, actor),
                ).fetchone()
                if row is None:
                    raise
                self.store.load(connection, row["payment_id"], actor)
        with self.store.transaction() as connection:
            events = [
                {"event": row["event"], "at": row["at"], "details": json.loads(row["details"])}
                for row in connection.execute(
                    "SELECT event,at,details FROM proposal_audit "
                    "WHERE proposal_id=? ORDER BY sequence",
                    (proposal_id,),
                )
            ]
            row = connection.execute(
                "SELECT payment_id FROM checkouts WHERE proposal_id=? AND user_id=?",
                (proposal_id, actor),
            ).fetchone()
        if row:
            for item in self.store.get_audit(row["payment_id"], actor_user_id=actor):
                events.append(
                    {
                        "event": item["event"],
                        "at": item["at"],
                        "details": json.loads(item["details"]),
                    }
                )
        return sorted(events, key=lambda item: datetime.fromisoformat(item["at"]))
