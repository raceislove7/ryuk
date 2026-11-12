"""Opt-in private demo provisioning. Defaults never enable financial access."""

import os
import sqlite3
from contextlib import AsyncExitStack
from urllib.parse import urlsplit

from fastapi import FastAPI
from pydantic import TypeAdapter

from app.schemas.catalog import CatalogSearchRequest
from app.schemas.policy import BudgetSnapshot, FinancialPolicy
from app.services.checkout import CheckoutService
from app.services.checkout_store import CheckoutAccessError, CheckoutStore
from app.services.durable_approvals import DurableApprovalService
from app.services.paypal import Identifier, PayPalError, PayPalSandboxAdapter, PayPalSettings
from app.services.session import DemoSessions
from app.services.workspace import WorkspaceService


async def provision(application: FastAPI, stack: AsyncExitStack) -> None:
    if os.environ.get("RYUK_DEMO_ENABLED") != "true":
        return
    stage = "RYUK_APP_ORIGIN: use an HTTPS origin or local HTTP localhost/127.0.0.1 origin"
    try:
        origin = os.environ["RYUK_APP_ORIGIN"].strip()
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        _ = parsed.port  # Reject malformed/out-of-range ports without echoing the URL.
        stage = "RYUK_DEMO_PASSWORD: set a private password of at least 16 characters"
        password = os.environ["RYUK_DEMO_PASSWORD"]
        if len(password) < 16:
            raise ValueError
        stage = "RYUK_SECURE_COOKIES: use true or false (false only for local HTTP)"
        secure = os.environ.get("RYUK_SECURE_COOKIES", "true")
        if secure not in {"true", "false"} or (parsed.scheme == "https" and secure != "true"):
            raise ValueError
        if secure == "false" and parsed.scheme != "http":
            raise ValueError  # HTTP is already restricted to loopback above.
        stage = "RYUK_BUDGET_LIMIT_MINOR: use an integer from 0 to 9223372036854775807"
        limit = int(os.environ.get("RYUK_BUDGET_LIMIT_MINOR", "150000"))
        if not 0 <= limit <= 9223372036854775807:
            raise ValueError
        stage = (
            "PAYPAL_MERCHANT_ID: use a Sandbox seller merchant ID, not an email or client secret"
        )
        merchant = os.environ.get("PAYPAL_MERCHANT_ID", "").strip()
        if merchant:
            TypeAdapter(Identifier).validate_python(merchant)
        stage = "RYUK_DEMO_PASSWORD: password hashing failed; check runtime memory/OpenSSL support"
        proxy_secret = os.environ.get("RYUK_PROXY_SHARED_SECRET", "")
        if proxy_secret and not 32 <= len(proxy_secret) <= 256:
            stage = "RYUK_PROXY_SHARED_SECRET: use 32 to 256 characters"
            raise ValueError
        auth = DemoSessions(
            password, origin=origin, secure=secure == "true", proxy_secret=proxy_secret or None
        )
        stage = "RYUK_CHECKOUT_DB_PATH: set a nonempty writable SQLite file path"
        path = os.environ["RYUK_CHECKOUT_DB_PATH"].strip()
        if not path:
            raise ValueError
        stage = "RYUK_CHECKOUT_DB_PATH: check directory/volume permissions and the SQLite file"
        store = CheckoutStore(path)
        try:
            store.get_budget(auth.actor)
        except CheckoutAccessError:
            store.create_account(
                BudgetSnapshot(
                    user_id=auth.actor,
                    currency="USD",
                    limit_minor=limit,
                    settled_minor=0,
                    reserved_minor=0,
                )
            )
            store.put_policy(
                FinancialPolicy(
                    user_id=auth.actor,
                    version="demo-policy-v1",
                    currency="USD",
                    max_amount_minor=150000,
                    approval_threshold_minor=130000,
                    allowed_merchant_ids=frozenset(
                        o.merchant_id
                        for o in application.state.catalog.search(CatalogSearchRequest()).offers
                    ),
                )
            )
        approvals = DurableApprovalService(store)
        application.state.workspace = WorkspaceService(application.state.catalog, store, approvals)
        if merchant:
            for offer in application.state.catalog.search(CatalogSearchRequest()).offers:
                store.map_merchant(offer.merchant_id, merchant)
        stage = "PayPal Sandbox HTTP client: check runtime TLS/certificate configuration"
        try:
            settings = PayPalSettings.from_env()
        except PayPalError:
            settings = None
        if settings is not None and merchant:
            paypal = await stack.enter_async_context(PayPalSandboxAdapter(settings))
            application.state.checkout_service = CheckoutService(store, approvals, paypal)
        application.state.demo_sessions = auth
    except (KeyError, ValueError, OSError, sqlite3.Error, OverflowError):
        raise RuntimeError(f"Ryuk demo startup failed — {stage}. Values omitted.") from None
