"""Actual HTTP client with mocked transport only: no live credentials or payments."""

import asyncio
import json
from copy import deepcopy

import httpx2
import pytest
from pydantic import ValidationError

from app.schemas import PaymentState
from app.services.paypal import (
    PayPalError,
    PayPalOrderTerms,
    PayPalSandboxAdapter,
    PayPalSettings,
    PayPalUncertain,
    map_order,
    request_id,
)

TERMS = PayPalOrderTerms(
    reference_id="payment_1",
    merchant_id="SANDBOXMERCHANT",
    amount_minor=118001,
    currency="USD",
)
SETTINGS = PayPalSettings(client_id="synthetic-client", client_secret="synthetic-secret")
TOKEN = {"access_token": "synthetic-token", "token_type": "Bearer", "expires_in": 300}


def order(status="APPROVED", capture_status=None):
    unit = {
        "reference_id": TERMS.reference_id,
        "payee": {"merchant_id": TERMS.merchant_id},
        "amount": TERMS.provider_amount(),
    }
    if capture_status:
        unit["payments"] = {
            "captures": [
                {
                    "id": "CAPTURE1",
                    "status": capture_status,
                    "amount": TERMS.provider_amount(),
                    "final_capture": True,
                }
            ]
        }
    return {"id": "ORDER1", "intent": "CAPTURE", "status": status, "purchase_units": [unit]}


def run(coro):
    return asyncio.run(coro)


def transport(handler):
    def wrapped(request):
        assert request.url.host == "api-m.sandbox.paypal.com"
        if request.url.path == "/v1/oauth2/token":
            assert request.headers["authorization"].startswith("Basic ")
            assert request.content == b"grant_type=client_credentials"
            return httpx2.Response(200, json=TOKEN)
        assert request.headers["authorization"] == "Bearer synthetic-token"
        return handler(request)

    return httpx2.MockTransport(wrapped)


@pytest.mark.parametrize("status", ["CREATED", "SAVED", "APPROVED", "PAYER_ACTION_REQUIRED"])
def test_open_order_mapping_and_capture_reconciliation(status):
    result = map_order(order(status), TERMS)
    assert result.state == PaymentState.AWAITING_PAYPAL_BUYER
    assert result.buyer_approved == (status == "APPROVED")
    assert (
        map_order(order(status), TERMS, capture_attempted=True).state
        == PaymentState.PENDING_PROVIDER
    )


@pytest.mark.parametrize(
    ("status", "capture", "expected"),
    [
        ("COMPLETED", "COMPLETED", PaymentState.SUCCEEDED),
        ("COMPLETED", "DECLINED", PaymentState.FAILED),
        ("COMPLETED", "FAILED", PaymentState.FAILED),
        ("COMPLETED", "PENDING", PaymentState.PENDING_PROVIDER),
        ("COMPLETED", "REFUNDED", PaymentState.PENDING_PROVIDER),
        ("COMPLETED", "PARTIALLY_REFUNDED", PaymentState.PENDING_PROVIDER),
        ("COMPLETED", "FUTURE", PaymentState.PENDING_PROVIDER),
        ("COMPLETED", None, PaymentState.PENDING_PROVIDER),
        ("VOIDED", None, PaymentState.FAILED),
        ("FUTURE", None, PaymentState.PENDING_PROVIDER),
        ("APPROVED", "COMPLETED", PaymentState.PENDING_PROVIDER),
    ],
)
def test_provider_mapping(status, capture, expected):
    assert map_order(order(status, capture), TERMS).state == expected


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(id="WRONG"),
        lambda p: p.update(intent="AUTHORIZE"),
        lambda p: p.update(purchase_units=[]),
        lambda p: p["purchase_units"].append(deepcopy(p["purchase_units"][0])),
        lambda p: p["purchase_units"][0].update(reference_id="wrong"),
        lambda p: p["purchase_units"][0].update(payee={"merchant_id": "wrong"}),
        lambda p: p["purchase_units"][0].update(
            amount={"value": "1180.02", "currency_code": "USD"}
        ),
        lambda p: p["purchase_units"][0]["amount"].update(currency_code="EUR"),
        lambda p: p["purchase_units"][0]["amount"].update(value=1180.01),
        lambda p: p["purchase_units"][0]["amount"].update(value="1.18001e3"),
        lambda p: p["purchase_units"][0]["amount"].update(value="1180.010"),
        lambda p: p["purchase_units"][0]["payments"]["captures"][0]["amount"].update(value="1"),
        lambda p: p["purchase_units"][0]["payments"]["captures"].append({}),
    ],
)
def test_binding_tampering_rejected(change):
    payload = order("COMPLETED", "COMPLETED")
    change(payload)
    with pytest.raises(PayPalError):
        map_order(payload, TERMS, order_id="ORDER1")


def test_partial_capture_not_success():
    payload = order("COMPLETED", "COMPLETED")
    payload["purchase_units"][0]["payments"]["captures"][0]["final_capture"] = False
    assert map_order(payload, TERMS).state == PaymentState.PENDING_PROVIDER


@pytest.mark.parametrize("amount", [True, 1.5, "100", 0, -1])
def test_money_strict(amount):
    with pytest.raises(ValidationError):
        PayPalOrderTerms(**(TERMS.model_dump() | {"amount_minor": amount}))


@pytest.mark.parametrize("currency", ["JPY", "INR", "usd"])
def test_unsupported_currency(currency):
    with pytest.raises(ValidationError):
        PayPalOrderTerms(**(TERMS.model_dump() | {"currency": currency}))


@pytest.mark.parametrize("currency", ["USD", "EUR"])
def test_exact_minor_unit_conversion(currency):
    t = PayPalOrderTerms(**(TERMS.model_dump() | {"currency": currency, "amount_minor": 1}))
    assert t.provider_amount() == {"currency_code": currency, "value": "0.01"}


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"PAYPAL_ENV": "live"},
        {"PAYPAL_BASE_URL": "https://evil.test"},
        {"PAYPAL_BASE_URL": "http://api-m.sandbox.paypal.com"},
    ],
)
def test_invalid_environment_sanitized(env):
    values = {"PAYPAL_CLIENT_ID": "private-id", "PAYPAL_CLIENT_SECRET": "private-secret"}
    if not env:
        values = {}
    with pytest.raises(PayPalError) as caught:
        PayPalSettings.from_env(values | env)
    assert "private" not in str(caught.value)


def test_settings_redacted_and_idempotency_stable():
    assert "synthetic-secret" not in repr(SETTINGS)
    assert "synthetic-client" not in repr(SETTINGS)
    assert request_id("capture", "stable") == request_id("capture", "stable")
    assert request_id("create", "stable") != request_id("capture", "stable")
    assert len(request_id("create", "stable")) == 36
    with pytest.raises(ValueError):
        request_id("capture", " ")


def test_create_get_capture_flow_and_stable_operation_headers():
    seen = []

    def handler(req):
        seen.append(req)
        if req.url.path.endswith("/capture"):
            assert json.loads(req.content) == {}
            return httpx2.Response(201, json=order("COMPLETED", "COMPLETED"))
        if req.method == "POST":
            assert json.loads(req.content) == {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": TERMS.reference_id,
                        "payee": {"merchant_id": TERMS.merchant_id},
                        "amount": TERMS.provider_amount(),
                    }
                ],
            }
            assert req.headers["prefer"] == "return=representation"
            return httpx2.Response(201, json=order("CREATED"))
        return httpx2.Response(200, json=order())

    async def scenario():
        async with PayPalSandboxAdapter(SETTINGS, transport=transport(handler)) as adapter:
            for _ in range(2):
                assert (
                    await adapter.create_order(TERMS, idempotency_key="same")
                ).order_id == "ORDER1"
            assert (
                await adapter.capture("ORDER1", TERMS, idempotency_key="same")
            ).state == "SUCCEEDED"

    run(scenario())
    assert seen[0].headers["paypal-request-id"] == seen[1].headers["paypal-request-id"]
    assert seen[-1].headers["paypal-request-id"] != seen[0].headers["paypal-request-id"]
    assert [r.method for r in seen] == ["POST", "POST", "GET", "POST"]


@pytest.mark.parametrize(
    "status,capture", [("CREATED", None), ("APPROVED", "PENDING"), ("FUTURE", None)]
)
def test_no_capture_without_verified_buyer_approval(status, capture):
    seen = []

    def handler(req):
        seen.append(req.method)
        return httpx2.Response(200, json=order(status, capture))

    async def scenario():
        async with PayPalSandboxAdapter(SETTINGS, transport=transport(handler)) as adapter:
            with pytest.raises(PayPalError):
                await adapter.capture("ORDER1", TERMS, idempotency_key="same")

    run(scenario())
    assert seen == ["GET"]


@pytest.mark.parametrize("capture,expected", [("COMPLETED", "SUCCEEDED"), ("DECLINED", "FAILED")])
def test_terminal_preflight_does_not_post(capture, expected):
    seen = []

    def handler(req):
        seen.append(req.method)
        return httpx2.Response(200, json=order("COMPLETED", capture))

    async def scenario():
        async with PayPalSandboxAdapter(SETTINGS, transport=transport(handler)) as adapter:
            assert (
                await adapter.capture("ORDER1", TERMS, idempotency_key="same")
            ).state == expected

    run(scenario())
    assert seen == ["GET"]


@pytest.mark.parametrize(
    "failure", ["timeout", "connect", "bad_json", "binding", 401, 422, 429, 500, 302]
)
def test_capture_uncertainty_no_automatic_retry_and_get_reconciliation(failure):
    calls = []
    captured = False

    def handler(req):
        nonlocal captured
        calls.append(req.method)
        if req.method == "GET":
            return httpx2.Response(
                200, json=order("COMPLETED", "COMPLETED") if captured else order()
            )
        captured = True
        if failure == "timeout":
            raise httpx2.ReadTimeout("private provider data", request=req)
        if failure == "connect":
            raise httpx2.ConnectError("private provider data", request=req)
        if failure == "bad_json":
            return httpx2.Response(201, content=b"not-json private provider data")
        if failure == "binding":
            payload = order("COMPLETED", "COMPLETED")
            payload["purchase_units"][0]["payee"]["merchant_id"] = "wrong"
            return httpx2.Response(201, json=payload)
        return httpx2.Response(
            failure,
            json={"message": "private provider data"},
            headers={"Location": "https://evil.test"},
        )

    async def scenario():
        async with PayPalSandboxAdapter(SETTINGS, transport=transport(handler)) as adapter:
            with pytest.raises(PayPalUncertain) as caught:
                await adapter.capture("ORDER1", TERMS, idempotency_key="same")
            assert caught.value.order_id == "ORDER1"
            assert caught.value.request_id == request_id("capture", "same")
            assert caught.value.state == "PENDING_PROVIDER"
            assert "private" not in str(caught.value)
            assert (
                await adapter.get_status("ORDER1", TERMS, capture_attempted=True)
            ).state == "SUCCEEDED"

    run(scenario())
    assert calls == ["GET", "POST", "GET"]


def test_create_timeout_keeps_request_id_without_fabricated_order():
    def handler(req):
        raise httpx2.ReadTimeout("private", request=req)

    async def scenario():
        async with PayPalSandboxAdapter(SETTINGS, transport=transport(handler)) as adapter:
            with pytest.raises(PayPalUncertain) as caught:
                await adapter.create_order(TERMS, idempotency_key="same")
            assert caught.value.order_id is None
            assert caught.value.request_id == request_id("create", "same")

    run(scenario())


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {**TOKEN, "expires_in": True},
        {**TOKEN, "token_type": "Basic"},
        {**TOKEN, "access_token": ""},
    ],
)
def test_malformed_oauth_no_order_request(body):
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return httpx2.Response(200, json=body)

    async def scenario():
        async with PayPalSandboxAdapter(
            SETTINGS, transport=httpx2.MockTransport(handler)
        ) as adapter:
            with pytest.raises(PayPalError, match="OAuth unavailable"):
                await adapter.create_order(TERMS, idempotency_key="same")

    run(scenario())
    assert calls == ["/v1/oauth2/token"]


def test_token_cache_expiry_concurrency_and_secret_safe_logs(caplog):
    now = [0.0]
    oauth = []

    def handler(req):
        if req.url.path == "/v1/oauth2/token":
            oauth.append(1)
            return httpx2.Response(200, json=TOKEN)
        return httpx2.Response(200, json=order())

    async def scenario():
        async with PayPalSandboxAdapter(
            SETTINGS, transport=httpx2.MockTransport(handler), clock=lambda: now[0]
        ) as adapter:
            await asyncio.gather(*(adapter.get_status("ORDER1", TERMS) for _ in range(4)))
            assert len(oauth) == 1
            now[0] = 270
            await adapter.get_status("ORDER1", TERMS)
            assert len(oauth) == 2

    run(scenario())
    assert "synthetic-secret" not in caplog.text
    assert "synthetic-token" not in caplog.text


@pytest.mark.parametrize("identifier", ["../oauth2/token", "ORDER1?foo=x", "https://evil.test", ""])
def test_invalid_order_id_never_dispatches(identifier):
    def handler(req):
        pytest.fail("Invalid ID must fail before any HTTP")

    async def scenario():
        async with PayPalSandboxAdapter(
            SETTINGS, transport=httpx2.MockTransport(handler)
        ) as adapter:
            with pytest.raises(PayPalError):
                await adapter.get_status(identifier, TERMS)

    run(scenario())


def test_status_failure_is_not_terminal_or_mutation():
    async def scenario():
        async with PayPalSandboxAdapter(
            SETTINGS,
            transport=transport(lambda req: httpx2.Response(404, json={"private": "details"})),
        ) as adapter:
            with pytest.raises(PayPalError, match="retain existing payment state"):
                await adapter.get_status("ORDER1", TERMS, capture_attempted=True)

    run(scenario())


def test_uncertain_capture_cannot_retry_when_provider_still_shows_approved():
    calls = []

    def handler(req):
        calls.append(req.method)
        if req.method == "GET":
            return httpx2.Response(200, json=order())
        raise httpx2.ReadTimeout("private", request=req)

    async def scenario():
        async with PayPalSandboxAdapter(SETTINGS, transport=transport(handler)) as adapter:
            with pytest.raises(PayPalUncertain):
                await adapter.capture("ORDER1", TERMS, idempotency_key="same")
            assert (await adapter.get_status("ORDER1", TERMS)).state == "PENDING_PROVIDER"
            with pytest.raises(PayPalError, match="not eligible"):
                await adapter.capture("ORDER1", TERMS, idempotency_key="same")

    run(scenario())
    assert calls == ["GET", "POST", "GET", "GET"]


def test_tampered_preflight_prevents_capture():
    calls = []

    def handler(req):
        calls.append(req.method)
        payload = order()
        payload["purchase_units"][0]["amount"]["value"] = "0.01"
        return httpx2.Response(200, json=payload)

    async def scenario():
        async with PayPalSandboxAdapter(SETTINGS, transport=transport(handler)) as adapter:
            with pytest.raises(PayPalError, match="binding"):
                await adapter.capture("ORDER1", TERMS, idempotency_key="same")

    run(scenario())
    assert calls == ["GET"]


@pytest.mark.parametrize("failure", ["timeout", 401, 500, 302])
def test_oauth_failure_never_sends_order(failure):
    paths = []

    def handler(req):
        paths.append(req.url.path)
        if failure == "timeout":
            raise httpx2.ReadTimeout("synthetic-secret", request=req)
        return httpx2.Response(failure, json={"message": "synthetic-secret"})

    async def scenario():
        async with PayPalSandboxAdapter(
            SETTINGS, transport=httpx2.MockTransport(handler)
        ) as adapter:
            with pytest.raises(PayPalError) as caught:
                await adapter.create_order(TERMS, idempotency_key="same")
            assert not isinstance(caught.value, PayPalUncertain)
            assert "synthetic-secret" not in str(caught.value)

    run(scenario())
    assert paths == ["/v1/oauth2/token"]


def test_unauthorized_status_invalidates_token_without_automatic_retry():
    paths = []

    def handler(req):
        paths.append(req.url.path)
        if req.url.path.endswith("token"):
            return httpx2.Response(200, json=TOKEN)
        return httpx2.Response(401, json={"message": "synthetic-secret"})

    async def scenario():
        async with PayPalSandboxAdapter(
            SETTINGS, transport=httpx2.MockTransport(handler)
        ) as adapter:
            for _ in range(2):
                with pytest.raises(PayPalError):
                    await adapter.get_status("ORDER1", TERMS)

    run(scenario())
    assert paths == ["/v1/oauth2/token", "/v2/checkout/orders/ORDER1"] * 2


@pytest.mark.parametrize("captures", [None, {}, "", 0, False])
def test_malformed_capture_collection_cannot_enable_capture(captures):
    payload = order()
    payload["purchase_units"][0]["payments"] = {"captures": captures}
    with pytest.raises(PayPalError):
        map_order(payload, TERMS)


def test_unknown_order_status_cannot_prove_failure():
    assert map_order(order("FUTURE", "FAILED"), TERMS).state == "PENDING_PROVIDER"
