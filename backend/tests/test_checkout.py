"""Full service-to-real-adapter mocked HTTP checkout; SQLite lives in pytest tmp_path."""

import asyncio
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx2
import pytest

from app.schemas import PurchaseIntent, PurchaseProposal
from app.schemas.policy import AttemptSnapshot, BudgetSnapshot, FinancialPolicy
from app.services.approvals import ApprovalAccessError, ApprovalPolicyError, InMemoryApprovalService
from app.services.catalog import CatalogService
from app.services.checkout import CheckoutBlocked, CheckoutService
from app.services.checkout_store import CheckoutAccessError, CheckoutStore
from app.services.paypal import PayPalSandboxAdapter, PayPalSettings
from app.services.verifier import verify_offer

NOW = datetime(2026, 11, 11, 15, tzinfo=timezone.utc)
ACTOR = {"actor_user_id": "user-1"}


def run(coro):
    return asyncio.run(coro)


class Sandbox:
    def __init__(self):
        self.calls = []
        self.orders = {}
        self.capture_mode = "success"
        self.create_mode = "success"
        self.on_get = None
        self.on_capture = None

    def payload(self, order_id):
        return deepcopy(self.orders[order_id])

    def approve(self, order_id):
        self.orders[order_id]["status"] = "APPROVED"

    def complete(self, order_id, status="COMPLETED"):
        payload = self.orders[order_id]
        payload["status"] = "COMPLETED"
        unit = payload["purchase_units"][0]
        unit["payments"] = {
            "captures": [
                {
                    "id": "CAP" + order_id,
                    "status": status,
                    "amount": deepcopy(unit["amount"]),
                    "final_capture": True,
                }
            ]
        }

    def handle(self, req):
        self.calls.append(req)
        if req.url.path.endswith("/token"):
            return httpx2.Response(
                200, json={"access_token": "fake-token", "token_type": "Bearer", "expires_in": 3600}
            )
        assert req.headers["authorization"] == "Bearer fake-token"
        if req.url.path == "/v2/checkout/orders":
            if self.create_mode == "timeout":
                raise httpx2.ReadTimeout("private", request=req)
            payload = json.loads(req.content)
            order_id = "ORDER" + str(len(self.orders) + 1)
            payload.update(id=order_id, status="CREATED")
            self.orders[order_id] = payload
            return httpx2.Response(201, json=self.payload(order_id))
        order_id = req.url.path.split("/")[4]
        if req.method == "GET":
            if self.on_get:
                self.on_get()
            return httpx2.Response(200, json=self.payload(order_id))
        if self.on_capture:
            self.on_capture()
        if self.capture_mode == "timeout":
            raise httpx2.ReadTimeout("private", request=req)
        if self.capture_mode == "timeout_after_capture":
            self.complete(order_id)
            raise httpx2.ReadTimeout("private", request=req)
        self.complete(
            order_id,
            {"success": "COMPLETED", "decline": "DECLINED", "pending": "PENDING"}[
                self.capture_mode
            ],
        )
        return httpx2.Response(201, json=self.payload(order_id))

    def capture_posts(self):
        return [r for r in self.calls if r.method == "POST" and r.url.path.endswith("/capture")]


@pytest.fixture
def env(tmp_path):
    now = [NOW]
    approvals = InMemoryApprovalService()
    store = CheckoutStore(tmp_path / "ledger.sqlite3")
    budget = BudgetSnapshot(
        user_id="user-1", currency="USD", limit_minor=300_000, settled_minor=0, reserved_minor=0
    )
    store.create_account(budget)
    policy = FinancialPolicy(
        user_id="user-1",
        version="v1",
        currency="USD",
        max_amount_minor=150_000,
        approval_threshold_minor=130_000,
        allowed_merchant_ids={"synthetic-hotel-merchant-001", "synthetic-hotel-merchant-002"},
    )
    store.put_policy(policy)
    store.map_merchant("synthetic-hotel-merchant-001", "DEMOSELLER")
    store.map_merchant("synthetic-hotel-merchant-002", "DEMOSELLER2")
    sandbox = Sandbox()
    paypal = PayPalSandboxAdapter(
        PayPalSettings(client_id="fake-id", client_secret="fake-secret"),
        transport=httpx2.MockTransport(sandbox.handle),
    )
    service = CheckoutService(store, approvals, paypal, clock=lambda: now[0])
    context = {
        "now": now,
        "approvals": approvals,
        "store": store,
        "policy": policy,
        "sandbox": sandbox,
        "paypal": paypal,
        "service": service,
    }
    context["proposal"] = register(context)
    yield context
    run(paypal.__aexit__())


def register(env, *, number="001", proposal_id=None):
    offer = CatalogService().get_offer("synthetic-hotel-" + number)
    intent = PurchaseIntent(
        category="hotel",
        query="Synthetic hotel with gym",
        currency="USD",
        budget_max_minor=150_000,
        approval_threshold_minor=130_000,
        required_attributes={"gym": True},
    )
    proposal = PurchaseProposal(
        proposal_id=proposal_id or str(uuid4()),
        user_id="user-1",
        intent=intent,
        offer=offer,
        policy_version="v1",
        created_at=NOW - timedelta(minutes=1),
        verification=verify_offer(intent, offer),
    )
    return env["approvals"].register_proposal(proposal, at=env["now"][0])


def grant(env, proposal):
    inputs = {
        **ACTOR,
        "policy": env["policy"],
        "budget": env["store"].get_budget("user-1"),
        "attempts": AttemptSnapshot(
            user_id="user-1", proposal_id=proposal.proposal_id, state="CLEAR"
        ),
    }
    request = env["approvals"].create_request(proposal.proposal_id, at=env["now"][0], **inputs)
    return env["approvals"].approve_request(request.approval_request_id, at=env["now"][0], **inputs)


async def ready(env, proposal=None):
    p = proposal or env["proposal"]
    result = await env["service"].create_checkout(p.proposal_id, **ACTOR)
    assert result.payment.state == "AWAITING_PAYPAL_BUYER"
    env["sandbox"].approve(result.order_id)
    return result


def test_checkout_success_exact_terms_durable_audit_and_reservation_before_post(env):
    async def scenario():
        record = await ready(env)
        payment_id = record.payment.payment_intent_id

        def before_post():
            budget = env["store"].get_budget("user-1")
            assert budget.reserved_minor == 118_000
            persisted = env["store"].get_checkout(payment_id, **ACTOR)
            assert persisted.payment.state == "CAPTURE_PENDING"
            events = [r["event"] for r in env["store"].get_audit(payment_id, **ACTOR)]
            assert events.index("BUDGET_RESERVED") < events.index("CAPTURE_DISPATCH")

        env["sandbox"].on_capture = before_post
        result = await env["service"].capture(payment_id, **ACTOR)
        assert result.payment.state == "SUCCEEDED"
        assert result.capture_id == "CAP" + record.order_id
        assert result.payment.proposal_digest == env["proposal"].proposal_digest
        budget = env["store"].get_budget("user-1")
        assert budget.settled_minor == 118_000 and budget.reserved_minor == 0
        assert env["store"].get_checkout(payment_id, **ACTOR) == result
        assert result.terms.amount_minor == 118_000
        assert result.terms.merchant_id == "DEMOSELLER"
        assert env["store"].get_audit(payment_id, **ACTOR)[-1]["event"] == "BUDGET_SETTLED"

    run(scenario())
    assert len(env["sandbox"].capture_posts()) == 1


def test_application_approval_and_paypal_buyer_approval_are_separate(env):
    p = register(env, number="002")

    async def scenario():
        with pytest.raises(ApprovalPolicyError):
            await env["service"].create_checkout(p.proposal_id, **ACTOR)
        assert not env["sandbox"].orders
        approval = grant(env, p)
        record = await env["service"].create_checkout(p.proposal_id, **ACTOR)
        assert record.payment.approval_request_id == approval.approval_request_id
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()
        assert env["store"].get_budget("user-1").reserved_minor == 0
        env["sandbox"].approve(record.order_id)
        result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert result.payment.state == "SUCCEEDED"

    run(scenario())


@pytest.mark.parametrize(
    "mutation", ["amount", "merchant", "currency", "offer", "snapshot", "intent", "policy_version"]
)
def test_canonical_changes_during_provider_preflight_block_capture(env, mutation):
    async def scenario():
        record = await ready(env)
        changed = env["proposal"].model_copy(deep=True)
        if mutation == "amount":
            changed.offer.amount_minor += 1
        elif mutation == "merchant":
            changed.offer.merchant_id = "other"
        elif mutation == "currency":
            changed.offer.currency = "EUR"
        elif mutation == "offer":
            changed.offer.offer_id = "other"
        elif mutation == "snapshot":
            changed.offer.evidence["gym"] = ["Changed evidence"]
        elif mutation == "intent":
            changed.intent.required_attributes["gym"] = False
        else:
            changed.policy_version = "v2"
        changed.verification = verify_offer(changed.intent, changed.offer)

        def update():
            env["approvals"].register_proposal(
                changed, at=env["now"][0], expected_digest=env["proposal"].proposal_digest
            )

        env["sandbox"].on_get = update
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()
        assert env["store"].get_budget("user-1").reserved_minor == 0

    run(scenario())


@pytest.mark.parametrize("change", ["policy_version", "policy_limit", "budget_limit", "mapping"])
def test_current_backend_policy_budget_and_mapping_are_reloaded_after_provider_get(env, change):
    async def scenario():
        record = await ready(env)

        def update():
            if change.startswith("policy"):
                policy = env["policy"].model_copy(deep=True)
                if change == "policy_version":
                    policy.version = "v2"
                else:
                    policy.max_amount_minor = 100_000
                    policy.approval_threshold_minor = 90_000
                env["store"].put_policy(policy)
            elif change == "budget_limit":
                env["store"].set_budget_limit("user-1", 100_000)
            else:
                env["store"].map_merchant(env["proposal"].offer.merchant_id, "DIFFERENTSELLER")

        env["sandbox"].on_get = update
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()
        assert env["store"].get_budget("user-1").reserved_minor == 0

    run(scenario())


def test_exact_approval_expiry_during_get_blocks_capture(env):
    p = register(env, number="002")
    approval = grant(env, p)

    async def scenario():
        record = await ready(env, p)
        env["sandbox"].on_get = lambda: env["now"].__setitem__(0, approval.expires_at)
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()

    run(scenario())


def test_latest_rejected_approval_cannot_be_hidden_by_old_approved_reference(env):
    p = register(env, number="002")
    grant(env, p)

    async def scenario():
        record = await ready(env, p)
        new = env["approvals"].create_request(
            p.proposal_id,
            at=NOW,
            **ACTOR,
            policy=env["policy"],
            budget=env["store"].get_budget("user-1"),
            attempts=AttemptSnapshot(user_id="user-1", proposal_id=p.proposal_id, state="CLEAR"),
        )
        env["approvals"].reject_request(new.approval_request_id, at=NOW, **ACTOR)
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()

    run(scenario())


def test_checkout_and_capture_retries_do_not_create_orders_or_double_settle(env):
    async def scenario():
        record = await ready(env)
        duplicate = await env["service"].create_checkout(env["proposal"].proposal_id, **ACTOR)
        assert duplicate == record
        result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert await env["service"].capture(record.payment.payment_intent_id, **ACTOR) == result
        assert await env["service"].reconcile(record.payment.payment_intent_id, **ACTOR) == result
        assert len(env["sandbox"].orders) == 1
        assert len(env["sandbox"].capture_posts()) == 1
        assert env["store"].get_budget("user-1").settled_minor == 118_000

    run(scenario())


@pytest.mark.parametrize(
    "result_state", ["success", "decline", "pending", "timeout", "timeout_after_capture"]
)
def test_capture_results_settle_release_or_hold(env, result_state):
    env["sandbox"].capture_mode = result_state

    async def scenario():
        record = await ready(env)
        result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        budget = env["store"].get_budget("user-1")
        if result_state == "success":
            assert result.payment.state == "SUCCEEDED"
            assert budget.settled_minor == 118_000 and budget.reserved_minor == 0
        elif result_state == "decline":
            assert result.payment.state == "FAILED"
            assert budget.settled_minor == 0 and budget.reserved_minor == 0
        else:
            assert result.payment.state == "PENDING_PROVIDER"
            assert budget.settled_minor == 0 and budget.reserved_minor == 118_000

    run(scenario())


def test_restart_retains_uncertainty_and_reconciliation_never_posts(env):
    env["sandbox"].capture_mode = "timeout"

    async def scenario():
        record = await ready(env)
        payment_id = record.payment.payment_intent_id
        await env["service"].capture(payment_id, **ACTOR)
        reopened = CheckoutStore(env["store"].path)
        # No restored authority: pending reconciliation must still account for prior capture.
        restarted = CheckoutService(
            reopened, InMemoryApprovalService(), env["paypal"], clock=lambda: NOW
        )
        pending = await restarted.capture(payment_id, **ACTOR)
        assert pending.payment.state == "PENDING_PROVIDER"
        assert reopened.get_budget("user-1").reserved_minor == 118_000
        env["sandbox"].complete(record.order_id)
        result = await restarted.reconcile(payment_id, **ACTOR)
        assert result.payment.state == "SUCCEEDED"
        assert reopened.get_budget("user-1").settled_minor == 118_000
        assert len(env["sandbox"].capture_posts()) == 1

    run(scenario())


def test_restart_without_approval_authority_cannot_dispatch_new_capture(env):
    async def scenario():
        record = await ready(env)
        restarted = CheckoutService(
            CheckoutStore(env["store"].path),
            InMemoryApprovalService(),
            env["paypal"],
            clock=lambda: NOW,
        )
        with pytest.raises(CheckoutBlocked):
            await restarted.capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()

    run(scenario())


def test_uncertain_create_is_persistent_and_never_automatically_retried(env):
    env["sandbox"].create_mode = "timeout"

    async def scenario():
        record = await env["service"].create_checkout(env["proposal"].proposal_id, **ACTOR)
        assert record.order_creation == "UNKNOWN" and record.order_id is None
        assert await env["service"].create_checkout(env["proposal"].proposal_id, **ACTOR) == record
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert sum(r.url.path == "/v2/checkout/orders" for r in env["sandbox"].calls) == 1
        assert env["store"].get_budget("user-1").reserved_minor == 0

    run(scenario())


def test_ownership_and_browser_term_inputs(env):
    async def scenario():
        with pytest.raises(ApprovalAccessError):
            await env["service"].create_checkout(
                env["proposal"].proposal_id, actor_user_id="other-user"
            )
        record = await ready(env)
        payment_id = record.payment.payment_intent_id
        with pytest.raises(CheckoutAccessError):
            await env["service"].capture(payment_id, actor_user_id="other-user")
        with pytest.raises(CheckoutAccessError):
            env["store"].get_audit(payment_id, actor_user_id="other-user")
        with pytest.raises(TypeError):
            await env["service"].capture(payment_id, **ACTOR, amount_minor=1, merchant_id="evil")
        # Mutation of returned objects never changes backend financial authority.
        record.terms = record.terms.model_copy(update={"amount_minor": 1, "merchant_id": "evil"})
        record.payment.amount_minor = 1
        result = await env["service"].capture(payment_id, **ACTOR)
        assert result.payment.amount_minor == 118_000 and result.terms.merchant_id == "DEMOSELLER"

    run(scenario())


def test_cancel_before_capture_only(env):
    async def scenario():
        record = await ready(env)
        canceled = env["service"].cancel(record.payment.payment_intent_id, **ACTOR)
        assert canceled.payment.state == "FAILED"
        assert await env["service"].capture(record.payment.payment_intent_id, **ACTOR) == canceled
        assert not env["sandbox"].capture_posts()

    run(scenario())


def test_pending_capture_cannot_cancel_or_release_reservation(env):
    env["sandbox"].capture_mode = "timeout"

    async def scenario():
        record = await ready(env)
        await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        with pytest.raises(CheckoutBlocked):
            env["service"].cancel(record.payment.payment_intent_id, **ACTOR)
        assert env["store"].get_budget("user-1").reserved_minor == 118_000

    run(scenario())


def test_two_connections_cannot_overspend_same_budget(env):
    env["store"].set_budget_limit("user-1", 200_000)
    other = register(env)

    async def scenario():
        one, two = await ready(env), await ready(env, other)
        second_store = CheckoutStore(env["store"].path)
        second = CheckoutService(second_store, env["approvals"], env["paypal"], clock=lambda: NOW)
        result = await env["service"].capture(one.payment.payment_intent_id, **ACTOR)
        assert result.payment.state == "SUCCEEDED"
        with pytest.raises(CheckoutBlocked):
            await second.capture(two.payment.payment_intent_id, **ACTOR)
        assert len(env["sandbox"].capture_posts()) == 1
        assert env["store"].get_budget("user-1").remaining_minor == 82_000

    run(scenario())


def test_failed_transaction_does_not_leave_partial_reservation_or_audit(env, monkeypatch):
    async def scenario():
        record = await ready(env)
        original = env["store"].audit

        def broken(connection, payment_id, event, at, details=None):
            if event == "CAPTURE_DISPATCH":
                raise sqlite3.OperationalError("simulated storage failure")
            original(connection, payment_id, event, at, details)

        monkeypatch.setattr(env["store"], "audit", broken)
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert env["store"].get_budget("user-1").reserved_minor == 0
        assert (
            env["store"].get_checkout(record.payment.payment_intent_id, **ACTOR).payment.state
            == "AWAITING_PAYPAL_BUYER"
        )
        assert not env["sandbox"].capture_posts()

    run(scenario())


def test_simultaneous_capture_handlers_dispatch_once_while_hold_is_in_flight(env):
    async def scenario():
        record = await ready(env)
        dispatched, release = asyncio.Event(), asyncio.Event()

        async def delayed(req):
            if req.method == "POST" and req.url.path.endswith("/capture"):
                dispatched.set()
                await release.wait()
            return env["sandbox"].handle(req)

        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=httpx2.MockTransport(delayed),
        ) as adapter:
            other = CheckoutService(
                CheckoutStore(env["store"].path), env["approvals"], adapter, clock=lambda: NOW
            )
            task = asyncio.create_task(other.capture(record.payment.payment_intent_id, **ACTOR))
            await asyncio.wait_for(dispatched.wait(), 2)
            pending = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
            assert pending.payment.state == "PENDING_PROVIDER"
            assert env["store"].get_budget("user-1").reserved_minor == 118_000
            release.set()
            result = await task
            assert result.payment.state == "SUCCEEDED"
            assert len(env["sandbox"].capture_posts()) == 1
            assert env["store"].get_budget("user-1").settled_minor == 118_000

    run(scenario())


def test_concurrent_different_proposals_cannot_spend_reserved_funds(env):
    env["store"].set_budget_limit("user-1", 200_000)
    second_proposal = register(env)

    async def scenario():
        one, two = await ready(env), await ready(env, second_proposal)
        dispatched, release = asyncio.Event(), asyncio.Event()

        async def delayed(req):
            if req.method == "POST" and req.url.path.endswith("/capture"):
                dispatched.set()
                await release.wait()
            return env["sandbox"].handle(req)

        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=httpx2.MockTransport(delayed),
        ) as adapter:
            first = CheckoutService(
                CheckoutStore(env["store"].path), env["approvals"], adapter, clock=lambda: NOW
            )
            task = asyncio.create_task(first.capture(one.payment.payment_intent_id, **ACTOR))
            await asyncio.wait_for(dispatched.wait(), 2)
            with pytest.raises(CheckoutBlocked):
                await env["service"].capture(two.payment.payment_intent_id, **ACTOR)
            assert env["store"].get_budget("user-1").reserved_minor == 118_000
            release.set()
            assert (await task).payment.state == "SUCCEEDED"
            assert len(env["sandbox"].capture_posts()) == 1

    run(scenario())


def test_cancelled_task_retains_hold_for_reconciliation(env):
    async def scenario():
        record = await ready(env)
        dispatched = asyncio.Event()

        async def delayed(req):
            if req.method == "POST" and req.url.path.endswith("/capture"):
                dispatched.set()
                await asyncio.Future()
            return env["sandbox"].handle(req)

        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=httpx2.MockTransport(delayed),
        ) as adapter:
            service = CheckoutService(env["store"], env["approvals"], adapter, clock=lambda: NOW)
            task = asyncio.create_task(service.capture(record.payment.payment_intent_id, **ACTOR))
            await asyncio.wait_for(dispatched.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            persisted = env["store"].get_checkout(record.payment.payment_intent_id, **ACTOR)
            assert persisted.payment.state == "PENDING_PROVIDER"
            assert env["store"].get_budget("user-1").reserved_minor == 118_000

    run(scenario())


def test_confirmed_external_capture_is_accounted_even_if_policy_now_denies(env):
    async def scenario():
        record = await ready(env)
        env["sandbox"].complete(record.order_id)
        env["store"].set_budget_limit("user-1", 0)
        result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert result.payment.state == "SUCCEEDED"
        assert not env["sandbox"].capture_posts()
        assert env["store"].get_budget("user-1").settled_minor == 118_000
        events = env["store"].get_audit(record.payment.payment_intent_id, **ACTOR)
        assert "EXTERNAL_CAPTURE_DISCOVERED" in [r["event"] for r in events]

    run(scenario())


def test_corrupt_digest_is_regenerated_and_rejected(env):
    async def scenario():
        record = await ready(env)
        env["approvals"]._proposals[env["proposal"].proposal_id].proposal_digest = "a" * 64
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()

    run(scenario())


def test_checkout_http_contract_and_owned_flow(env):
    from fastapi.testclient import TestClient

    from app.api.checkout import get_checkout_actor, get_checkout_service
    from app.main import app

    app.dependency_overrides[get_checkout_actor] = lambda: "user-1"
    app.dependency_overrides[get_checkout_service] = lambda: env["service"]
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/checkouts", json={"proposal_id": env["proposal"].proposal_id}
            )
            assert response.status_code == 200
            view = response.json()
            checkout_id = view["checkout_id"]
            env["sandbox"].approve(view["paypal_order_id"])
            assert client.get(f"/v1/checkouts/{checkout_id}").status_code == 200
            response = client.post(f"/v1/checkouts/{checkout_id}/capture", json={})
            assert response.status_code == 200 and response.json()["state"] == "SUCCEEDED"
            assert response.json()["amount_minor"] == 118_000
            assert "fake-secret" not in response.text and "fake-token" not in response.text
            assert "idempotency_key" not in response.json() and "user_id" not in response.json()
            assert (
                client.post(f"/v1/checkouts/{checkout_id}/reconcile", json={}).json()["state"]
                == "SUCCEEDED"
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "extra",
    [
        {"amount_minor": 1},
        {"merchant_id": "evil"},
        {"user_id": "user-1"},
        {"state": "SUCCEEDED"},
        {"paypal_order_id": "other"},
        {"approved": True},
    ],
)
def test_http_rejects_browser_authority_fields(env, extra):
    from fastapi.testclient import TestClient

    from app.api.checkout import get_checkout_actor, get_checkout_service
    from app.main import app

    app.dependency_overrides[get_checkout_actor] = lambda: "user-1"
    app.dependency_overrides[get_checkout_service] = lambda: env["service"]
    try:
        with TestClient(app) as client:
            assert (
                client.post(
                    "/v1/checkouts", json={"proposal_id": env["proposal"].proposal_id, **extra}
                ).status_code
                == 422
            )
            response = client.post("/v1/checkouts/some-id/capture", json=extra)
            assert response.status_code == 422
            assert not env["sandbox"].calls
    finally:
        app.dependency_overrides.clear()


def test_http_default_auth_fails_closed_ignoring_identity_headers():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/v1/checkouts",
            json={"proposal_id": "any"},
            headers={"X-User-Id": "user-1", "Authorization": "Bearer invented"},
        )
        assert response.status_code == 503
        assert client.get("/health").status_code == 200


def test_simultaneous_create_returns_claim_without_duplicate_provider_order(env):
    async def scenario():
        dispatched, release = asyncio.Event(), asyncio.Event()

        async def delayed(req):
            if req.url.path == "/v2/checkout/orders":
                dispatched.set()
                await release.wait()
            return env["sandbox"].handle(req)

        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=httpx2.MockTransport(delayed),
        ) as adapter:
            first = CheckoutService(env["store"], env["approvals"], adapter, clock=lambda: NOW)
            task = asyncio.create_task(first.create_checkout(env["proposal"].proposal_id, **ACTOR))
            await asyncio.wait_for(dispatched.wait(), 2)
            duplicate = await env["service"].create_checkout(env["proposal"].proposal_id, **ACTOR)
            assert duplicate.order_creation == "CREATING"
            release.set()
            record = await task
            assert record.payment.payment_intent_id == duplicate.payment.payment_intent_id
            assert len(env["sandbox"].orders) == 1

    run(scenario())


def test_pending_reconciles_original_terms_even_when_current_authority_changes(env):
    env["sandbox"].capture_mode = "timeout"

    async def scenario():
        record = await ready(env)
        await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        env["store"].set_budget_limit("user-1", 0)
        env["store"].map_merchant(env["proposal"].offer.merchant_id, "NEWSELLER")
        changed = env["proposal"].model_copy(deep=True)
        changed.offer.amount_minor = 120_000
        changed.verification = verify_offer(changed.intent, changed.offer)
        env["approvals"].register_proposal(
            changed, at=NOW, expected_digest=env["proposal"].proposal_digest
        )
        env["sandbox"].complete(record.order_id)
        result = await env["service"].reconcile(record.payment.payment_intent_id, **ACTOR)
        assert result.payment.state == "SUCCEEDED"
        assert result.payment.amount_minor == 118_000
        assert env["store"].get_budget("user-1").settled_minor == 118_000
        assert len(env["sandbox"].capture_posts()) == 1

    run(scenario())


def test_reconciliation_unavailable_retains_reservation(env):
    env["sandbox"].capture_mode = "timeout"

    async def scenario():
        record = await ready(env)
        await env["service"].capture(record.payment.payment_intent_id, **ACTOR)

        def unavailable():
            raise httpx2.ReadTimeout("private details")

        env["sandbox"].on_get = unavailable
        result = await env["service"].reconcile(record.payment.payment_intent_id, **ACTOR)
        assert result.payment.state == "PENDING_PROVIDER"
        assert env["store"].get_budget("user-1").reserved_minor == 118_000
        assert len(env["sandbox"].capture_posts()) == 1

    run(scenario())


def test_provider_binding_mismatch_during_preflight_blocks_capture(env):
    async def scenario():
        record = await ready(env)
        env["sandbox"].orders[record.order_id]["purchase_units"][0]["payee"]["merchant_id"] = "EVIL"
        with pytest.raises(CheckoutBlocked):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert not env["sandbox"].capture_posts()
        assert env["store"].get_budget("user-1").reserved_minor == 0

    run(scenario())


def test_store_does_not_allow_memory_only_ledger_or_imported_holds(tmp_path):
    with pytest.raises(ValueError):
        CheckoutStore(":memory:")
    store = CheckoutStore(tmp_path / "ledger.sqlite3")
    with pytest.raises(ValueError):
        store.create_account(
            BudgetSnapshot(
                user_id="u", currency="USD", limit_minor=100, settled_minor=0, reserved_minor=1
            )
        )


def test_settlement_storage_failure_rolls_back_and_reconciles_without_recapture(env, monkeypatch):
    async def scenario():
        record = await ready(env)
        original = env["store"].save

        def broken(connection, updated):
            if updated.payment.state == "SUCCEEDED":
                raise sqlite3.OperationalError("simulated commit-path storage failure")
            original(connection, updated)

        monkeypatch.setattr(env["store"], "save", broken)
        with pytest.raises(sqlite3.OperationalError):
            await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        budget = env["store"].get_budget("user-1")
        assert budget.settled_minor == 0 and budget.reserved_minor == 118_000
        assert len(env["sandbox"].capture_posts()) == 1
        monkeypatch.setattr(env["store"], "save", original)
        result = await env["service"].reconcile(record.payment.payment_intent_id, **ACTOR)
        assert result.payment.state == "SUCCEEDED"
        assert env["store"].get_budget("user-1").settled_minor == 118_000
        assert len(env["sandbox"].capture_posts()) == 1

    run(scenario())


def test_http_other_owner_gets_not_found_without_dispatch(env):
    from fastapi.testclient import TestClient

    from app.api.checkout import get_checkout_actor, get_checkout_service
    from app.main import app

    record = run(ready(env))
    app.dependency_overrides[get_checkout_actor] = lambda: "other-user"
    app.dependency_overrides[get_checkout_service] = lambda: env["service"]
    try:
        with TestClient(app) as client:
            path = f"/v1/checkouts/{record.payment.payment_intent_id}"
            assert client.get(path).status_code == 404
            assert client.post(path + "/capture", json={}).status_code == 404
            assert not env["sandbox"].capture_posts()
    finally:
        app.dependency_overrides.clear()
