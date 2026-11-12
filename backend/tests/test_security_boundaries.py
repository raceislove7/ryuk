"""Regression evidence for confirmed review findings; synthetic credentials only."""
# ruff: noqa: F811

import pytest
from test_workspace import ORIGIN, PASSWORD, client, investigate, login  # noqa: F401

from app.api.agent import get_intent_parser
from app.main import app
from app.services.intent_parser import IntentClarificationRequired
from app.services.proposal_binding import canonical_proposal_digest
from app.services.session import DemoSessions


def test_anonymous_parser_never_calls_model(client):
    calls = []

    class Parser:
        async def parse(self, query):
            calls.append(query)
            raise AssertionError("Model must not be invoked")

    app.dependency_overrides[get_intent_parser] = lambda: Parser()
    result = client.post("/v1/agent/parse", json={"query": "private request"}, headers=ORIGIN)
    assert result.status_code == 401
    assert not calls


@pytest.mark.parametrize(
    "path,body",
    [
        ("/v1/session", {"password": "private-sentinel-" * 100}),
        ("/v1/session", {"password": {"private-sentinel": "credential"}}),
        ("/v1/session", {"password": PASSWORD, "private-sentinel": "credential"}),
        ("/v1/requests", {"query": "private-sentinel-" * 1000}),
    ],
)
def test_validation_never_reflects_secret_input(client, path, body):
    login(client)
    response = client.post(path, json=body, headers=ORIGIN)
    assert response.status_code == 422
    assert "private-sentinel" not in response.text
    assert PASSWORD not in response.text


def test_clarification_exception_not_reflected(client):
    login(client)

    class Parser:
        async def parse(self, query):
            raise IntentClarificationRequired("private-sentinel-provider-credential")

    app.dependency_overrides[get_intent_parser] = lambda: Parser()
    response = client.post("/v1/agent/parse", json={"query": "request"}, headers=ORIGIN)
    assert response.status_code == 422
    assert "private-sentinel" not in response.text


def test_every_model_candidate_requires_explicit_review(client):
    candidates = investigate(client)
    for candidate in candidates:
        assert candidate["proposal"]["intent_review_required"] is True
        if candidate["policy"]["decision"] != "DENY":
            assert candidate["policy"]["decision"] == "REQUIRE_APPROVAL"
            assert "INTENT_REVIEW_REQUIRED" in candidate["policy"]["reason_codes"]
            assert (
                client.post(
                    "/v1/checkouts",
                    json={"proposal_id": candidate["proposal"]["proposal_id"]},
                    headers=ORIGIN,
                ).status_code
                == 409
            )


def test_review_marker_is_digest_bound(client):
    candidate = investigate(client)[0]
    proposal = app.state.workspace.approvals.get_proposal(
        candidate["proposal"]["proposal_id"], actor_user_id="ryuk-demo-buyer"
    )
    changed = proposal.model_copy(update={"intent_review_required": False})
    assert canonical_proposal_digest(changed) != proposal.proposal_digest


@pytest.mark.parametrize("origin", ["https://demo.example", "https://localhost"])
def test_https_cannot_use_insecure_cookie(origin):
    with pytest.raises(ValueError, match="secure cookies"):
        DemoSessions(PASSWORD, origin=origin, secure=False)


def test_session_allocation_bounded():
    auth = DemoSessions(PASSWORD, origin="https://demo.example")
    auth._sessions = {str(i).encode(): float("inf") for i in range(64)}
    assert auth.login(PASSWORD, "client") is None
    for i in range(1024):
        auth._attempts[str(i)]
    assert auth.login(PASSWORD, "new-client") is None


def test_model_limit_does_not_disable_status_or_financial_recovery(client):
    login(client)
    auth = app.state.demo_sessions
    for _ in range(10):
        assert auth.allow_model_request()
    assert not auth.allow_model_request()
    response = client.post("/v1/requests", json={"query": "request"}, headers=ORIGIN)
    assert response.status_code == 429
    assert client.get("/v1/workspace").status_code == 200
