"""Mandatory-attribute acceptance must deny execution, not only return a policy label."""
# ruff: noqa: F811

from test_workspace import ORIGIN, client, investigate  # noqa: F401


def test_mandatory_requirement_denial_never_dispatches_provider(client):
    candidates = investigate(client)
    failed = next(
        item
        for item in candidates
        if item["proposal"]["offer"]["offer_id"] == "synthetic-hotel-004"
    )
    assert failed["proposal"]["offer"]["amount_minor"] == 98000
    assert failed["policy"]["decision"] == "DENY"
    assert "REQUIRED_ATTRIBUTE_FAILED" in failed["policy"]["reason_codes"]
    assert "BUDGET_EXCEEDED" not in failed["policy"]["reason_codes"]
    pid = failed["proposal"]["proposal_id"]
    for endpoint, body in [
        (f"/v1/proposals/{pid}/approval", {}),
        ("/v1/checkouts", {"proposal_id": pid}),
    ]:
        assert client.post(endpoint, json=body, headers=ORIGIN).status_code == 409
    assert not client.sandbox.calls
    budget = client.get("/v1/workspace").json()["budget"]
    assert budget["settled_minor"] == budget["reserved_minor"] == 0
