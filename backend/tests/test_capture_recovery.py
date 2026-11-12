"""Explicit decline evidence and operator GET-only recovery; no live provider calls."""

# ruff: noqa: F811

import httpx2
import pytest
from test_checkout import ACTOR, env, ready, run  # noqa: F401

from app.recover_checkout import inspect_holds, recover_checkout
from app.services.checkout_store import CheckoutStore
from app.services.paypal import PayPalSandboxAdapter, PayPalSettings


def declining_transport(  # noqa: F811
    env, *, code="INSTRUMENT_DECLINED", unavailable=False, captured=False, error_body=None
):
    original = env["sandbox"].handle
    dispatched = False

    def handle(req):
        nonlocal dispatched
        if req.method == "POST" and req.url.path.endswith("/capture"):
            env["sandbox"].calls.append(req)
            dispatched = True
            if captured:
                env["sandbox"].complete(
                    req.url.path.split("/")[4], "PENDING" if captured == "pending" else "COMPLETED"
                )
            return httpx2.Response(
                422,
                json=error_body
                if error_body is not None
                else {
                    "name": "UNPROCESSABLE_ENTITY",
                    "message": "private provider data",
                    "details": [{"issue": code}],
                },
            )
        if req.method == "GET" and dispatched and unavailable:
            return httpx2.Response(500)
        return original(req)

    return httpx2.MockTransport(handle)


@pytest.mark.parametrize("code", ["INSTRUMENT_DECLINED", "UNKNOWN_ERROR", "ORDER_ALREADY_CAPTURED"])
def test_decline_release_requires_explicit_verified_evidence(env, code):  # noqa: F811
    async def scenario():
        record = await ready(env)
        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=declining_transport(env, code=code),
        ) as paypal:
            env["service"].paypal = paypal
            result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        budget = env["store"].get_budget("user-1")
        if code == "INSTRUMENT_DECLINED":
            assert result.payment.state == "FAILED"
            assert result.capture_decline_code == code
            assert budget.reserved_minor == 0
        else:
            assert result.payment.state == "PENDING_PROVIDER"
            assert budget.reserved_minor == 118000
        assert budget.settled_minor == 0
        assert len(env["sandbox"].capture_posts()) == 1

    run(scenario())


def test_operator_recovers_persisted_decline_after_restart_once(env):  # noqa: F811
    async def scenario():
        record = await ready(env)
        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=declining_transport(env, unavailable=True),
        ) as paypal:
            env["service"].paypal = paypal
            result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
            assert result.payment.state == "PENDING_PROVIDER"
        path = env["store"].path
        before = path.read_bytes()
        holds = inspect_holds(path)
        assert holds[0]["decline_evidence"] == "INSTRUMENT_DECLINED"
        assert before == path.read_bytes()
        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=httpx2.MockTransport(env["sandbox"].handle),
        ) as paypal:
            for _ in range(2):
                outcome = await recover_checkout(
                    path,
                    record.payment.payment_intent_id,
                    paypal,
                    operator="test-operator",
                    reason="verified decline",
                )
                assert outcome["state"] == "FAILED"
        assert len(env["sandbox"].capture_posts()) == 1
        budget = CheckoutStore(path).get_budget("user-1")
        assert budget.reserved_minor == budget.settled_minor == 0
        events = env["store"].get_audit(record.payment.payment_intent_id, **ACTOR)
        assert sum(e["event"] == "BUDGET_RELEASED" for e in events) == 1
        assert any(e["event"] == "OPERATOR_RECONCILIATION_REQUESTED" for e in events)
        assert "private provider data" not in str(events)

    run(scenario())


def test_confirmed_capture_wins_over_decline_evidence(env):  # noqa: F811
    async def scenario():
        record = await ready(env)
        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=declining_transport(env, captured=True),
        ) as paypal:
            env["service"].paypal = paypal
            result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
            assert result.payment.state == "SUCCEEDED"
        assert env["store"].get_budget("user-1").settled_minor == 118000

    run(scenario())


def test_operator_does_not_release_an_inconclusive_hold(env):  # noqa: F811
    async def scenario():
        record = await ready(env)
        env["sandbox"].capture_mode = "timeout"
        await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        outcome = await recover_checkout(
            env["store"].path,
            record.payment.payment_intent_id,
            env["paypal"],
            operator="test",
            reason="status check",
        )
        assert not outcome["resolved"]
        assert env["store"].get_budget("user-1").reserved_minor == 118000
        assert len(env["sandbox"].capture_posts()) == 1

    run(scenario())


def test_missing_ledger_is_never_created(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(ValueError):
        inspect_holds(path)
    assert not path.exists()


@pytest.mark.parametrize(
    "error_body",
    [
        {"name": "UNPROCESSABLE_ENTITY", "details": []},
        {"name": "OTHER", "details": [{"issue": "INSTRUMENT_DECLINED"}]},
        {
            "name": "UNPROCESSABLE_ENTITY",
            "details": [{"issue": "INSTRUMENT_DECLINED"}, {"issue": "UNKNOWN"}],
        },
        [],
    ],
)
def test_non_definitive_error_shape_retains_hold(env, error_body):  # noqa: F811
    async def scenario():
        record = await ready(env)
        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=declining_transport(env, error_body=error_body),
        ) as paypal:
            env["service"].paypal = paypal
            result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert result.capture_decline_code is None
        assert result.payment.state == "PENDING_PROVIDER"
        assert env["store"].get_budget("user-1").reserved_minor == 118000

    run(scenario())


def test_pending_capture_prevents_decline_release(env):  # noqa: F811
    async def scenario():
        record = await ready(env)
        async with PayPalSandboxAdapter(
            PayPalSettings(client_id="fake", client_secret="fake"),
            transport=declining_transport(env, captured="pending"),
        ) as paypal:
            env["service"].paypal = paypal
            result = await env["service"].capture(record.payment.payment_intent_id, **ACTOR)
        assert result.payment.state == "PENDING_PROVIDER"
        assert env["store"].get_budget("user-1").reserved_minor == 118000

    run(scenario())
