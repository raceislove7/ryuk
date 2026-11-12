"""Internal Sandbox-only Orders v2 adapter; never a public financial authority.

Callers own authenticated consent, canonical merchant mapping, policy, reservations,
operation-key persistence and state/audit transactions. No automatic mutation retries.
"""

import asyncio
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Annotated, Any, Literal
from uuid import NAMESPACE_URL, uuid5

import httpx2
from pydantic import ConfigDict, Field, SecretStr, StringConstraints, model_validator

from app.schemas import PaymentState
from app.schemas.domain import Currency, DomainModel, MinorUnits

SANDBOX_URL = "https://api-m.sandbox.paypal.com"
Identifier = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_-]{1,127}$")]
# Deliberately limited to the two currencies in the synthetic hotel demo. No FX.
CURRENCIES = frozenset({"USD", "EUR"})


class PayPalError(RuntimeError):
    """Sanitized adapter failure. Never includes provider bodies or credentials."""


class PayPalUncertain(PayPalError):
    """A mutation may have taken effect: persist uncertainty and reconcile first."""

    def __init__(self, order_id: str | None, request_id: str) -> None:
        super().__init__("PayPal outcome uncertain; reconcile before any mutation retry")
        self.order_id = order_id
        self.request_id = request_id
        self.state = PaymentState.PENDING_PROVIDER


class PayPalCaptureDeclined(PayPalError):
    """Authenticated capture response explicitly rejected this dispatch's instrument."""

    def __init__(self, order_id: str, operation_key: str) -> None:
        super().__init__("PayPal capture instrument declined; verify order before release")
        self.order_id = order_id
        self.request_id = operation_key
        self.code = "INSTRUMENT_DECLINED"


class PayPalSettings(DomainModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    environment: Literal["sandbox"] = "sandbox"
    base_url: Literal["https://api-m.sandbox.paypal.com"] = SANDBOX_URL
    client_id: SecretStr = Field(min_length=1)
    client_secret: SecretStr = Field(min_length=1)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "PayPalSettings":
        values = os.environ if env is None else env
        try:
            return cls(
                environment=values.get("PAYPAL_ENV", "sandbox"),
                base_url=values.get("PAYPAL_BASE_URL", SANDBOX_URL),
                client_id=values.get("PAYPAL_CLIENT_ID", ""),
                client_secret=values.get("PAYPAL_CLIENT_SECRET", ""),
            )
        except ValueError:
            raise PayPalError("Valid backend PayPal Sandbox configuration required") from None


class PayPalOrderTerms(DomainModel):
    """Trusted backend mapping, not browser input or synthetic merchant IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    reference_id: Identifier
    merchant_id: Identifier
    amount_minor: MinorUnits = Field(gt=0)
    currency: Currency

    @model_validator(mode="after")
    def supported_currency(self) -> "PayPalOrderTerms":
        if self.currency not in CURRENCIES:
            raise ValueError("Adapter supports USD/EUR only; no implicit currency conversion")
        return self

    def provider_amount(self) -> dict[str, str]:
        return {
            "currency_code": self.currency,
            "value": f"{self.amount_minor // 100}.{self.amount_minor % 100:02d}",
        }


@dataclass(frozen=True)
class PayPalOrderResult:
    order_id: str
    provider_status: str
    state: PaymentState
    buyer_approved: bool
    capture_id: str | None = None
    capture_absent: bool = False


def request_id(operation: Literal["create", "capture"], key: str) -> str:
    """Stable per-operation UUID; caller must persist key and its immutable terms."""
    if operation not in {"create", "capture"} or not isinstance(key, str) or not key.strip():
        raise ValueError("Nonempty stable operation key required")
    return str(uuid5(NAMESPACE_URL, f"agentpay/paypal/sandbox/{operation}/{key}"))


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,127}", value):
        raise PayPalError("Invalid PayPal resource identifier")
    return value


def _amount_matches(value: Any, terms: PayPalOrderTerms) -> bool:
    if not isinstance(value, dict) or value.get("currency_code") != terms.currency:
        return False
    text = value.get("value")
    if not isinstance(text, str) or not re.fullmatch(r"\d{1,16}(?:\.\d{1,2})?", text):
        return False
    whole, _, fraction = text.partition(".")
    return int(whole) * 100 + int(fraction.ljust(2, "0")) == terms.amount_minor


def map_order(
    payload: Any,
    terms: PayPalOrderTerms,
    *,
    order_id: str | None = None,
    capture_attempted: bool = False,
) -> PayPalOrderResult:
    """Verify exact single-unit binding before mapping an authenticated response.

    COMPLETED order alone is never success. Unknown/refunded/partial results need
    investigation. Reconciliation cannot turn an open order into a failed capture.
    """
    terms = PayPalOrderTerms.model_validate(terms.model_dump())
    try:
        actual_id = _identifier(payload["id"])
        units = payload["purchase_units"]
        if order_id is not None and actual_id != order_id:
            raise ValueError
        if payload["intent"] != "CAPTURE" or not isinstance(units, list) or len(units) != 1:
            raise ValueError
        unit = units[0]
        if (
            unit["reference_id"] != terms.reference_id
            or unit["payee"]["merchant_id"] != terms.merchant_id
            or not _amount_matches(unit["amount"], terms)
        ):
            raise ValueError
        status = payload["status"]
        if not isinstance(status, str):
            raise ValueError
        captures = unit.get("payments", {}).get("captures", [])
        if not isinstance(captures, list):
            raise ValueError
        state = PaymentState.PENDING_PROVIDER
        capture_id = None
        if captures:
            if len(captures) != 1:
                raise ValueError
            capture = captures[0]
            capture_id = _identifier(capture["id"])
            if not _amount_matches(capture["amount"], terms):
                raise ValueError
            if (
                status == "COMPLETED"
                and capture["status"] == "COMPLETED"
                and capture.get("final_capture") is True
            ):
                state = PaymentState.SUCCEEDED
            elif status in {
                "CREATED",
                "SAVED",
                "APPROVED",
                "VOIDED",
                "COMPLETED",
                "PAYER_ACTION_REQUIRED",
            } and capture["status"] in {"DECLINED", "FAILED"}:
                state = PaymentState.FAILED
        elif status == "VOIDED":
            state = PaymentState.FAILED
        elif status in {"CREATED", "SAVED", "APPROVED", "PAYER_ACTION_REQUIRED"}:
            if not capture_attempted:
                state = PaymentState.AWAITING_PAYPAL_BUYER
        return PayPalOrderResult(
            actual_id, status, state, status == "APPROVED", capture_id, not captures
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        raise PayPalError("PayPal order binding or representation invalid") from None


class PayPalSandboxAdapter:
    """Owns a private HTTP client. Use as async context manager; mock via transport."""

    def __init__(
        self,
        settings: PayPalSettings,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._settings = PayPalSettings.model_validate(settings.model_dump())
        self._client = httpx2.AsyncClient(
            base_url=SANDBOX_URL,
            transport=transport,
            timeout=httpx2.Timeout(15, connect=5),
            follow_redirects=False,
        )
        self._clock = clock
        self._token: SecretStr | None = None
        self._expires = 0.0
        self._token_lock = asyncio.Lock()
        self._uncertain_orders: set[str] = set()

    async def __aenter__(self) -> "PayPalSandboxAdapter":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self._client.aclose()

    async def _access_token(self) -> str:
        async with self._token_lock:
            if self._token is not None and self._clock() < self._expires:
                return self._token.get_secret_value()
            started = self._clock()
            try:
                response = await self._client.post(
                    "/v1/oauth2/token",
                    data={"grant_type": "client_credentials"},
                    auth=httpx2.BasicAuth(
                        self._settings.client_id.get_secret_value(),
                        self._settings.client_secret.get_secret_value(),
                    ),
                    headers={"Accept": "application/json"},
                )
                if response.status_code != 200:
                    raise ValueError
                body = response.json()
                token, expires = body["access_token"], body["expires_in"]
                if (
                    body["token_type"].lower() != "bearer"
                    or not isinstance(token, str)
                    or not token
                    or any(c.isspace() for c in token)
                    or type(expires) is not int
                    or expires <= 0
                ):
                    raise ValueError
                self._token = SecretStr(token)
                self._expires = started + max(0, expires - 30)
                return token
            except (httpx2.HTTPError, ValueError, KeyError, TypeError, AttributeError):
                raise PayPalError("PayPal OAuth unavailable") from None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        key: str | None = None,
        body: dict | None = None,
        order_id: str | None = None,
        before_dispatch: Callable[[], None] | None = None,
    ) -> Any:
        token = await self._access_token()  # Failure before dispatch is not a capture timeout.
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        if key is not None:
            headers["PayPal-Request-Id"] = key
        # The coordinator commits authorization/reservation after OAuth and provider preflight.
        if before_dispatch is not None:
            before_dispatch()
        try:
            response = await self._client.request(method, path, headers=headers, json=body)
            if response.status_code == 401:
                self._token = None  # Refresh on the next explicit operation; never replay POST.
            if (
                method == "POST"
                and order_id is not None
                and key is not None
                and path == f"/v2/checkout/orders/{order_id}/capture"
                and response.status_code == 422
            ):
                error = response.json()
                details = error.get("details") if isinstance(error, dict) else None
                if (
                    isinstance(error, dict)
                    and error.get("name") == "UNPROCESSABLE_ENTITY"
                    and isinstance(details, list)
                    and len(details) == 1
                    and isinstance(details[0], dict)
                    and details[0].get("issue") == "INSTRUMENT_DECLINED"
                ):
                    raise PayPalCaptureDeclined(order_id, key)
            if response.status_code not in ({200} if method == "GET" else {200, 201}):
                raise ValueError
            return response.json()
        except (httpx2.HTTPError, ValueError):
            if method == "POST":
                raise PayPalUncertain(order_id, key) from None
            raise PayPalError("PayPal status unavailable; retain existing payment state") from None

    async def create_order(
        self,
        terms: PayPalOrderTerms,
        *,
        idempotency_key: str,
    ) -> PayPalOrderResult:
        terms = PayPalOrderTerms.model_validate(terms.model_dump())
        key = request_id("create", idempotency_key)
        body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": terms.reference_id,
                    "amount": terms.provider_amount(),
                    "payee": {"merchant_id": terms.merchant_id},
                }
            ],
        }
        payload = await self._request("POST", "/v2/checkout/orders", key=key, body=body)
        try:
            return map_order(payload, terms)
        except PayPalError:
            raise PayPalUncertain(None, key) from None

    async def get_status(
        self,
        order_id: str,
        terms: PayPalOrderTerms,
        *,
        capture_attempted: bool = False,
    ) -> PayPalOrderResult:
        order_id = _identifier(order_id)
        terms = PayPalOrderTerms.model_validate(terms.model_dump())
        payload = await self._request("GET", f"/v2/checkout/orders/{order_id}")
        uncertain = capture_attempted or order_id in self._uncertain_orders
        result = map_order(payload, terms, order_id=order_id, capture_attempted=uncertain)
        if result.state in {PaymentState.SUCCEEDED, PaymentState.FAILED}:
            self._uncertain_orders.discard(order_id)
        return result

    async def capture(
        self,
        order_id: str,
        terms: PayPalOrderTerms,
        *,
        idempotency_key: str,
        before_capture: Callable[[], None] | None = None,
    ) -> PayPalOrderResult:
        order_id = _identifier(order_id)
        terms = PayPalOrderTerms.model_validate(terms.model_dump())
        key = request_id("capture", idempotency_key)
        # Preflight verifies binding and provider buyer consent, never browser callbacks.
        current = await self.get_status(order_id, terms)
        if current.state in {PaymentState.SUCCEEDED, PaymentState.FAILED}:
            return current
        if (
            order_id in self._uncertain_orders
            or not current.buyer_approved
            or current.capture_id is not None
        ):
            raise PayPalError("PayPal order is not eligible for capture")
        try:
            payload = await self._request(
                "POST",
                f"/v2/checkout/orders/{order_id}/capture",
                key=key,
                body={},
                order_id=order_id,
                before_dispatch=before_capture,
            )
        except (PayPalUncertain, PayPalCaptureDeclined):
            self._uncertain_orders.add(order_id)
            raise
        try:
            result = map_order(payload, terms, order_id=order_id, capture_attempted=True)
        except PayPalError:
            self._uncertain_orders.add(order_id)
            raise PayPalUncertain(order_id, key) from None
        if result.state == PaymentState.PENDING_PROVIDER:
            self._uncertain_orders.add(order_id)
        return result
