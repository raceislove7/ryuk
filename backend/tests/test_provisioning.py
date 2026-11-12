"""Startup diagnostics identify settings without logging their private values."""

import asyncio
import sqlite3
from contextlib import AsyncExitStack

import pytest
from fastapi import FastAPI

from app.services.catalog import CatalogService
from app.services.provisioning import provision


@pytest.fixture
def settings(monkeypatch, tmp_path):
    values = {
        "RYUK_DEMO_ENABLED": "true",
        "RYUK_APP_ORIGIN": "http://localhost:3000",
        "RYUK_DEMO_PASSWORD": "synthetic-private-startup-password",
        "RYUK_SECURE_COOKIES": "false",
        "RYUK_CHECKOUT_DB_PATH": str(tmp_path / "ledger.sqlite3"),
        "RYUK_BUDGET_LIMIT_MINOR": "150000",
        "PAYPAL_MERCHANT_ID": "",
        "PAYPAL_CLIENT_ID": "",
        "PAYPAL_CLIENT_SECRET": "",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


def boot():
    async def run():
        application = FastAPI()
        application.state.catalog = CatalogService()
        async with AsyncExitStack() as stack:
            await provision(application, stack)
        return application

    return asyncio.run(run())


@pytest.mark.parametrize(
    "key,value",
    [
        ("RYUK_DEMO_PASSWORD", ""),
        ("RYUK_DEMO_PASSWORD", "too-short"),
        ("RYUK_APP_ORIGIN", "localhost:3000"),
        ("RYUK_APP_ORIGIN", "http://untrusted.example:3000"),
        ("RYUK_APP_ORIGIN", "https://private-user:private-pass@example.com"),
        ("RYUK_APP_ORIGIN", "https://example.com/path"),
        ("RYUK_APP_ORIGIN", "http://localhost:99999"),
        ("RYUK_SECURE_COOKIES", "no"),
        ("RYUK_BUDGET_LIMIT_MINOR", "1,500"),
        ("RYUK_BUDGET_LIMIT_MINOR", "-1"),
        ("RYUK_BUDGET_LIMIT_MINOR", "9223372036854775808"),
        ("PAYPAL_MERCHANT_ID", "private-merchant@example.com"),
        ("RYUK_CHECKOUT_DB_PATH", ""),
    ],
)
def test_named_error_omits_input_values(settings, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError) as caught:
        boot()
    message = str(caught.value)
    assert key in message and "Values omitted" in message
    assert settings["RYUK_DEMO_PASSWORD"] not in message
    if value and value not in {"-1", "no"}:
        assert value not in message
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("key", ["RYUK_APP_ORIGIN", "RYUK_DEMO_PASSWORD", "RYUK_CHECKOUT_DB_PATH"])
def test_missing_required_setting_identified(settings, monkeypatch, key):
    monkeypatch.delenv(key)
    with pytest.raises(RuntimeError, match=key):
        boot()


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:3000", "http://127.0.0.1:3000", "http://[::1]:3000", "https://demo.example"],
)
def test_valid_origins_start_without_provider_credentials(settings, monkeypatch, origin):
    monkeypatch.setenv("RYUK_APP_ORIGIN", origin)
    monkeypatch.setenv("RYUK_SECURE_COOKIES", "true" if origin.startswith("https") else "false")
    assert boot().state.demo_sessions.origin == origin


def test_sqlite_failure_is_identified_without_raw_path(settings, monkeypatch):
    def unavailable(path):
        raise sqlite3.OperationalError("private filesystem details")

    monkeypatch.setattr("app.services.provisioning.CheckoutStore", unavailable)
    with pytest.raises(RuntimeError, match="RYUK_CHECKOUT_DB_PATH") as caught:
        boot()
    assert "private filesystem details" not in str(caught.value)
    assert settings["RYUK_CHECKOUT_DB_PATH"] not in str(caught.value)
