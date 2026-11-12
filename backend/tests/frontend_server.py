"""E2E-only server with fake model/provider transport. Never used by application startup."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import mkdtemp

import httpx2
import uvicorn
from fastapi import Request
from fastapi.responses import RedirectResponse
from test_checkout import Sandbox

from app.api.agent import get_intent_parser
from app.main import app, lifespan
from app.schemas.catalog import CatalogSearchRequest
from app.schemas.policy import BudgetSnapshot
from app.services.checkout_store import CheckoutStore
from app.services.durable_approvals import DurableApprovalService
from app.services.intent_parser import FakeIntentParser
from app.services.paypal import PayPalSandboxAdapter, PayPalSettings
from app.services.session import DemoSessions
from app.services.workspace import WorkspaceService

if os.environ.get("RYUK_E2E_TEST_ONLY") != "1":
    raise RuntimeError("Explicit RYUK_E2E_TEST_ONLY=1 is required for test fixtures")
PASSWORD = "synthetic-browser-password"


def new_ledger_path() -> str:
    """Always create a new isolated directory; never accept a preexisting database."""
    directory = Path(mkdtemp(prefix="ryuk-e2e-", dir=os.environ.get("RYUK_E2E_ROOT")))
    return str(directory / "ledger.sqlite3")


os.environ.update(
    RYUK_DEMO_ENABLED="true",
    RYUK_DEMO_PASSWORD=PASSWORD,
    RYUK_APP_ORIGIN="http://localhost:3100",
    RYUK_SECURE_COOKIES="false",
    RYUK_CHECKOUT_DB_PATH=new_ledger_path(),
    PAYPAL_ENV="sandbox",
    PAYPAL_BASE_URL="https://api-m.sandbox.paypal.com",
    PAYPAL_CLIENT_ID="synthetic-browser-client",
    PAYPAL_CLIENT_SECRET="synthetic-browser-secret",
    PAYPAL_MERCHANT_ID="DEMOSELLER",
)
cases = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures/intent_prompts.json").read_text()
)
gold = cases["cases"][0]
QUERY = (
    "Find a hotel in Switzerland for 5 nights under USD 1,500.\n"
    "Gym, mountain view and free cancellation are required.\n"
    "Private pool preferred. Ask me above USD 1,300."
)
# Quotes must match the actual prompt. Real fake parser runs the real Pydantic/source checks.
example = json.loads(json.dumps(gold["extraction"]))
example["budget"]["quote"] = "under USD 1,500"
for attribute in example["required_attributes"]:
    if attribute["name"] in {"gym", "mountain_view", "free_cancellation"}:
        attribute["quote"] = "Gym, mountain view and free cancellation are required"
parser = FakeIntentParser({gold["query"]: gold["extraction"], QUERY: example})
app.dependency_overrides[get_intent_parser] = lambda: parser
sandbox = Sandbox()
redirect_visits = 0


@app.middleware("http")
async def proxy_redirect_fixture(request: Request, call_next):
    if (
        request.url.path == "/v1/session"
        and request.cookies.get("synthetic_proxy_mode") == "redirect"
    ):
        return RedirectResponse("http://127.0.0.1:8100/__test__/redirect-target")
    return await call_next(request)


@app.get("/__test__/redirect-target")
def redirect_target() -> dict:
    global redirect_visits
    redirect_visits += 1
    return {"visits": redirect_visits}


@app.get("/__test__/redirect-visits")
def redirect_count() -> dict:
    return {"visits": redirect_visits}


@asynccontextmanager
async def e2e_lifespan(application):
    async with lifespan(application):
        async with PayPalSandboxAdapter(
            PayPalSettings.from_env(),
            transport=httpx2.MockTransport(lambda req: sandbox.handle(req)),
        ) as paypal:
            application.state.checkout_service.paypal = paypal
            yield


# Test-only route simulates the SDK's provider approval, not browser financial authority.
@app.post("/__test__/approve/{order_id}")
def test_approve(order_id: str, mode: str = "success") -> dict:
    sandbox.approve(order_id)
    sandbox.capture_mode = mode
    return {"ok": True}


@app.post("/__test__/new-case")
def test_new_case() -> dict:
    global sandbox
    previous = app.state.workspace.store
    actor = app.state.demo_sessions.actor
    with previous.transaction() as connection:
        policy = previous.policy(connection, actor)
    store = CheckoutStore(new_ledger_path())
    store.create_account(
        BudgetSnapshot(
            user_id=actor, currency="USD", limit_minor=150000, settled_minor=0, reserved_minor=0
        )
    )
    store.put_policy(policy)
    for offer in app.state.catalog.search(CatalogSearchRequest()).offers:
        store.map_merchant(offer.merchant_id, "DEMOSELLER")
    approvals = DurableApprovalService(store)
    app.state.workspace = WorkspaceService(app.state.catalog, store, approvals)
    app.state.checkout_service.approvals = approvals
    app.state.checkout_service.store = store
    app.state.demo_sessions = DemoSessions(PASSWORD, origin="http://localhost:3100", secure=False)
    sandbox = Sandbox()
    return {"ok": True}


app.router.lifespan_context = e2e_lifespan
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="warning")
