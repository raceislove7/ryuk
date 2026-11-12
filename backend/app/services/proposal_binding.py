"""Versioned canonical proposal hashing; no approval, payment, or I/O authority."""

import hashlib
import hmac
import json
from datetime import timezone

from app.schemas import PurchaseProposal
from app.services.verifier import verify_offer

DIGEST_FORMAT = "agentpay-proposal-v2"


class InvalidProposalBinding(ValueError):
    """A proposal lacks a current verification snapshot or matching stored digest."""


def canonical_proposal_digest(proposal: PurchaseProposal) -> str:
    """Hash exact canonical identity/terms and a freshly checked verification reference."""
    proposal = PurchaseProposal.model_validate(proposal.model_dump(warnings=False))
    if proposal.verification is None or proposal.verification != verify_offer(
        proposal.intent, proposal.offer
    ):
        raise InvalidProposalBinding("A current canonical verification snapshot is required.")
    payload = {
        "format": DIGEST_FORMAT,
        "original_and_parsed_intent": proposal.intent.model_dump(mode="json"),
        "proposal_id": proposal.proposal_id,
        "created_at": proposal.created_at.astimezone(timezone.utc).isoformat(
            timespec="microseconds"
        ),
        "user_id": proposal.user_id,
        "offer_id": proposal.offer.offer_id,
        "merchant_id": proposal.offer.merchant_id,
        "amount_minor": proposal.offer.amount_minor,
        "currency": proposal.offer.currency,
        "policy_version": proposal.policy_version,
        "verification_snapshot_id": proposal.verification.verification_snapshot_id,
        "intent_review_required": proposal.intent_review_required,
    }
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def bind_proposal(proposal: PurchaseProposal) -> PurchaseProposal:
    """Create a validated copy with a fresh digest; never silently approve changed terms."""
    proposal = PurchaseProposal.model_validate(proposal.model_dump(warnings=False))
    data = proposal.model_dump(warnings=False)
    data["proposal_digest"] = canonical_proposal_digest(proposal)
    return PurchaseProposal.model_validate(data)


def require_proposal_binding(proposal: PurchaseProposal) -> None:
    """Regenerate and compare; a SHA-shaped string alone never establishes a binding."""
    proposal = PurchaseProposal.model_validate(proposal.model_dump(warnings=False))
    expected = canonical_proposal_digest(proposal)
    if proposal.proposal_digest is None or not hmac.compare_digest(
        proposal.proposal_digest, expected
    ):
        raise InvalidProposalBinding("Proposal terms no longer match the canonical digest.")
