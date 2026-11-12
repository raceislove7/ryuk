"""Exact source provenance without live model calls or changes to spending authority."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from test_intent_parser import GOLD
from test_workspace import client, investigate  # noqa: F401

from app.schemas import PurchaseIntent, PurchaseProposal
from app.services.approvals import InMemoryApprovalService, ProposalConflictError
from app.services.catalog import CatalogService
from app.services.intent_parser import FakeIntentParser, InvalidParserOutput
from app.services.proposal_binding import bind_proposal
from app.services.verifier import verify_offer


def parsed():
    return asyncio.run(FakeIntentParser({GOLD["query"]: GOLD["extraction"]}).parse(GOLD["query"]))


@pytest.mark.parametrize("mutation", ["quote", "offset", "role", "name", "duplicate", "missing"])
def test_bad_provenance_rejected_at_domain_boundary(mutation):
    data = parsed().model_dump()
    source = data["requirement_sources"][0]
    if mutation == "quote":
        source["quote"] = "Invented requirement"
    elif mutation == "offset":
        source["start"] += 1
    elif mutation == "role":
        source["role"] = "preferred"
    elif mutation == "name":
        source["name"] = "unparsed"
    elif mutation == "duplicate":
        data["requirement_sources"].append(deepcopy(source))
    else:
        data["requirement_sources"].pop()
    with pytest.raises(ValidationError):
        PurchaseIntent.model_validate(data)


def test_legacy_intent_serialization_and_proposal_binding_remain_compatible():
    legacy = PurchaseIntent.model_validate(GOLD["expected"])
    assert legacy.model_dump() == GOLD["expected"]
    assert '"requirement_sources"' not in legacy.model_dump_json()
    offer = CatalogService().get_offer("synthetic-hotel-001")
    proposal = bind_proposal(
        PurchaseProposal(
            proposal_id="legacy-source-compat",
            user_id="test",
            intent=legacy,
            offer=offer,
            policy_version="v1",
            created_at=datetime.now(timezone.utc),
            verification=verify_offer(legacy, offer),
        )
    )
    restored = PurchaseProposal.model_validate_json(proposal.model_dump_json())
    assert bind_proposal(restored).proposal_digest == proposal.proposal_digest


def test_source_associations_are_bound_to_snapshot_and_proposal_digest():
    intent = parsed()
    offer = CatalogService().get_offer("synthetic-hotel-001")
    original = bind_proposal(
        PurchaseProposal(
            proposal_id="quote-binding",
            user_id="test",
            intent=intent,
            offer=offer,
            policy_version="v1",
            created_at=datetime.now(timezone.utc),
            verification=verify_offer(intent, offer),
        )
    )
    changed = original.model_copy(deep=True)
    # Removing provenance is a different review representation, not reusable consent.
    changed.intent.requirement_sources = []
    changed.verification = verify_offer(changed.intent, offer)
    assert (
        changed.verification.verification_snapshot_id
        != original.verification.verification_snapshot_id
    )
    assert bind_proposal(changed).proposal_digest != original.proposal_digest
    approvals = InMemoryApprovalService()
    approvals.register_proposal(original, at=original.created_at)
    with pytest.raises(ProposalConflictError):
        approvals.register_proposal(changed, at=original.created_at)


def test_workspace_response_retains_sources_on_canonical_proposals(client):  # noqa: F811
    candidates = investigate(client)
    intent = candidates[0]["proposal"]["intent"]
    assert intent["requirement_sources"]
    for source in intent["requirement_sources"]:
        assert intent["query"][source["start"] : source["end"]] == source["quote"]
    response = client.get("/v1/proposals/" + candidates[0]["proposal"]["proposal_id"])
    assert (
        response.json()["proposal"]["intent"]["requirement_sources"]
        == intent["requirement_sources"]
    )


def test_fabricated_parser_quote_is_still_rejected():
    raw = deepcopy(GOLD["extraction"])
    raw["required_attributes"][0]["quote"] = "Made up source text"
    with pytest.raises(InvalidParserOutput):
        asyncio.run(FakeIntentParser({GOLD["query"]: raw}).parse(GOLD["query"]))


def test_span_cannot_extend_past_end_even_when_python_slice_matches():
    with pytest.raises(ValidationError):
        PurchaseIntent(
            category="hotel",
            query="Gym required",
            currency="USD",
            budget_max_minor=100,
            approval_threshold_minor=0,
            required_attributes={"gym": True},
            requirement_sources=[
                {"role": "required", "name": "gym", "quote": "Gym required", "start": 0, "end": 99}
            ],
        )


def test_parser_spans_count_unicode_code_points_not_utf16():
    query = "🏔 " + GOLD["query"]
    intent = asyncio.run(FakeIntentParser({query: GOLD["extraction"]}).parse(query))
    for source in intent.requirement_sources:
        assert source.start == query.index(source.quote)
        assert query[source.start : source.end] == source.quote
