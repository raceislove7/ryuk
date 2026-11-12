"""Authenticated frontend integration over real services, synthetic parser and mocked HTTP."""

import asyncio
import json
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient
from test_checkout import Sandbox

from app.api.agent import get_intent_parser
from app.main import app
from app.services.intent_parser import FakeIntentParser
from app.services.paypal import PayPalSandboxAdapter, PayPalSettings
from app.services.session import COOKIE_NAME, DemoSessions

PASSWORD = "synthetic-workspace-password"
ORIGIN = {"Origin": "http://localhost:3100"}
GOLD = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures/intent_prompts.json").read_text()
)["cases"][0]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("RYUK_DEMO_ENABLED", "true")
    monkeypatch.setenv("RYUK_DEMO_PASSWORD", PASSWORD)
    monkeypatch.setenv("RYUK_APP_ORIGIN", "http://localhost:3100")
    monkeypatch.setenv("RYUK_SECURE_COOKIES", "false")
    monkeypatch.setenv("RYUK_CHECKOUT_DB_PATH", str(tmp_path / "checkout.sqlite3"))
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "synthetic-client")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "synthetic-private-secret")
    monkeypatch.setenv("PAYPAL_MERCHANT_ID", "DEMOSELLER")
    app.dependency_overrides[get_intent_parser] = lambda: FakeIntentParser(
        {GOLD["query"]: GOLD["extraction"]}
    )
    sandbox = Sandbox()
    paypal = PayPalSandboxAdapter(
        PayPalSettings.from_env(), transport=httpx2.MockTransport(sandbox.handle)
    )
    try:
        with TestClient(app) as test:
            app.state.checkout_service.paypal = paypal
            test.sandbox = sandbox
            yield test
    finally:
        app.dependency_overrides.clear()
        asyncio.run(paypal.__aexit__())


def login(client):
    response = client.post("/v1/session", json={"password": PASSWORD}, headers=ORIGIN)
    assert response.status_code == 200
    return response


def investigate(client):
    login(client)
    response = client.post("/v1/requests", json={"query": GOLD["query"]}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return response.json()["candidates"]


def test_real_authentication_cookie_logout_and_financial_data_privacy(client):
    assert client.get("/v1/session").json() == {"configured": True, "authenticated": False}
    assert client.get("/v1/workspace").status_code == 401
    assert client.get("/v1/workspace", headers={"X-User-Id": "ryuk-demo-buyer"}).status_code == 401
    response = login(client)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    workspace = client.get("/v1/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["budget"]["limit_minor"] == 150000
    assert "synthetic-private-secret" not in workspace.text
    assert PASSWORD not in workspace.text
    assert client.delete("/v1/session", headers=ORIGIN).status_code == 200
    assert client.get("/v1/workspace").status_code == 401


@pytest.mark.parametrize("origin", [None, "https://evil.test", "http://localhost:3100.evil.test"])
def test_csrf_and_login_origin_enforced(client, origin):
    headers = {"Origin": origin} if origin else {}
    assert (
        client.post("/v1/session", json={"password": PASSWORD}, headers=headers).status_code == 403
    )
    login(client)
    assert (
        client.post("/v1/requests", json={"query": GOLD["query"]}, headers=headers).status_code
        == 403
    )


def test_password_guess_rate_limit_and_forged_session(client):
    client.cookies.set(COOKIE_NAME, "forged-session")
    assert client.get("/v1/workspace").status_code == 401
    for _ in range(5):
        assert (
            client.post("/v1/session", json={"password": "wrong"}, headers=ORIGIN).status_code
            == 401
        )
    assert (
        client.post("/v1/session", json={"password": PASSWORD}, headers=ORIGIN).status_code == 401
    )


def test_expired_session_and_secure_cookie_configuration(monkeypatch):
    auth = DemoSessions(PASSWORD, origin="https://demo.example", secure=True)
    token = auth.login(PASSWORD, "local")
    assert auth.actor_for(token) == "ryuk-demo-buyer"
    monkeypatch.setattr("app.services.session.monotonic", lambda: 1e20)
    assert auth.actor_for(token) is None


def test_shortlist_verification_policy_all_come_from_backend(client):
    candidates = investigate(client)
    assert len(candidates) >= 3
    assert [x["policy"]["decision"] for x in candidates[:3]] == [
        "REQUIRE_APPROVAL",
        "REQUIRE_APPROVAL",
        "DENY",
    ]
    assert candidates[0]["required_verified"] == candidates[0]["required_total"] == 5
    assert all(c["evidence"] for c in candidates[0]["proposal"]["verification"]["required_checks"])
    assert candidates[0]["proposal"]["verification"]["preference_score"] == 0
    assert not client.sandbox.orders
    assert "INTENT_REVIEW_REQUIRED" in candidates[0]["policy"]["reason_codes"]


def test_approval_ui_backend_to_order_capture_and_audit(client):
    candidate = investigate(client)[1]
    pid = candidate["proposal"]["proposal_id"]
    assert (
        client.post("/v1/checkouts", json={"proposal_id": pid}, headers=ORIGIN).status_code == 409
    )
    response = client.post(f"/v1/proposals/{pid}/approval", json={}, headers=ORIGIN)
    approval = response.json()
    assert approval["amount_minor"] == 139000 and approval["status"] == "PENDING"
    aid = approval["approval_request_id"]
    assert (
        client.post(
            f"/v1/approvals/{aid}/decision", json={"decision": "APPROVE"}, headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.get(f"/v1/proposals/{pid}").json()["policy"]["decision"]
        == "ALLOW_ELIGIBLE_FOR_CHECKOUT"
    )
    record = client.post("/v1/checkouts", json={"proposal_id": pid}, headers=ORIGIN).json()
    cid, order_id = record["checkout_id"], record["paypal_order_id"]
    client.sandbox.approve(order_id)
    paid = client.post(f"/v1/checkouts/{cid}/capture", json={}, headers=ORIGIN)
    assert paid.status_code == 200 and paid.json()["state"] == "SUCCEEDED"
    assert paid.json()["capture_id"] and paid.json()["verification_snapshot_id"]
    assert client.get("/v1/workspace").json()["budget"]["settled_minor"] == 139000
    events = client.get(f"/v1/proposals/{pid}/audit").json()["events"]
    names = [item["event"] for item in events]
    for expected in [
        "USER_INTENT_CREATED",
        "OFFERS_FOUND",
        "VERIFICATION_COMPLETED",
        "POLICY_EVALUATED",
        "APPROVAL_GRANTED",
        "PAYPAL_ORDER_CREATED",
        "CAPTURE_DISPATCH",
        "BUDGET_SETTLED",
    ]:
        assert expected in names
    assert "synthetic-private-secret" not in json.dumps(events)


@pytest.mark.parametrize(
    "extra",
    [
        {"amount_minor": 1},
        {"merchant_id": "evil"},
        {"policy_version": "forged"},
        {"user_id": "other"},
        {"intent": {"budget_max_minor": 999999999}},
    ],
)
def test_request_api_cannot_accept_browser_authority(client, extra):
    login(client)
    response = client.post("/v1/requests", json={"query": GOLD["query"], **extra}, headers=ORIGIN)
    assert response.status_code == 422
    assert not client.sandbox.orders


def test_blocked_offer_and_rejected_approval_never_reach_checkout(client):
    candidates = investigate(client)
    denied = candidates[2]["proposal"]["proposal_id"]
    assert (
        client.post("/v1/checkouts", json={"proposal_id": denied}, headers=ORIGIN).status_code
        == 409
    )
    assert (
        client.post(f"/v1/proposals/{denied}/approval", json={}, headers=ORIGIN).status_code == 409
    )
    pid = candidates[1]["proposal"]["proposal_id"]
    aid = client.post(f"/v1/proposals/{pid}/approval", json={}, headers=ORIGIN).json()[
        "approval_request_id"
    ]
    assert (
        client.post(
            f"/v1/approvals/{aid}/decision", json={"decision": "REJECT"}, headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.post("/v1/checkouts", json={"proposal_id": pid}, headers=ORIGIN).status_code == 409
    )
    assert not client.sandbox.orders


def test_unknown_owned_record_is_not_found(client):
    login(client)
    assert client.get("/v1/proposals/nonexistent").status_code == 404
    assert client.get("/v1/proposals/nonexistent/audit").status_code == 404


def test_unconfigured_parser_has_no_production_fake_fallback(client):
    login(client)
    app.dependency_overrides.pop(get_intent_parser)
    assert (
        client.post("/v1/requests", json={"query": GOLD["query"]}, headers=ORIGIN).status_code
        == 503
    )
