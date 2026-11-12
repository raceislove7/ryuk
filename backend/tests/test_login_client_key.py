"""Trust-boundary and availability checks for proxy-aware login throttling."""

from collections import deque

import pytest
from starlette.requests import Request
from test_workspace import ORIGIN, PASSWORD, client  # noqa: F401

from app.services.client_key import login_client_key
from app.services.session import DemoSessions

SECRET = "synthetic-proxy-channel-secret-32-characters"


def request(headers=None, peer="127.0.0.1"):
    return Request(
        {
            "type": "http",
            "client": (peer, 1234),
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        }
    )


def test_forwarded_headers_cannot_choose_direct_client_key():
    assert (
        login_client_key(
            request(
                {
                    "X-Forwarded-For": "1.2.3.4",
                    "Forwarded": "for=1.2.3.4",
                    "X-Real-IP": "1.2.3.4",
                    "X-Ryuk-Client-IP": "1.2.3.4",
                    "X-Ryuk-Proxy-Token": "wrong",
                }
            ),
            SECRET,
        )
        == "peer:127.0.0.1"
    )


@pytest.mark.parametrize("value", ["", "1.2.3.4, 5.6.7.8", "garbage", "127.0.0.1:80"])
def test_invalid_assertions_use_peer(value):
    assert (
        login_client_key(
            request(
                {
                    "X-Ryuk-Proxy-Token": SECRET,
                    "X-Ryuk-Client-IP": value,
                }
            ),
            SECRET,
        )
        == "peer:127.0.0.1"
    )


def test_normalizes_equivalent_ip_addresses():
    def key(ip):
        return login_client_key(
            request(
                {
                    "X-Ryuk-Proxy-Token": SECRET,
                    "X-Ryuk-Client-IP": ip,
                }
            ),
            SECRET,
        )

    assert key("::ffff:192.0.2.1") == key("192.0.2.1")
    assert key("2001:0db8:0:0:0:0:0:1") == key("2001:db8::1")


def test_one_proxy_client_cannot_lock_out_another(client):  # noqa: F811
    client.app.state.demo_sessions.proxy_secret = SECRET

    def headers(ip, token=SECRET):
        return {**ORIGIN, "X-Ryuk-Client-IP": ip, "X-Ryuk-Proxy-Token": token}

    for _ in range(5):
        assert (
            client.post(
                "/v1/session", json={"password": "wrong"}, headers=headers("192.0.2.1")
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/v1/session", json={"password": PASSWORD}, headers=headers("192.0.2.1")
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/session", json={"password": PASSWORD}, headers=headers("192.0.2.2")
        ).status_code
        == 200
    )
    # Spoofed browser assertions cannot rotate the fallback peer's allowance.
    for i in range(5):
        assert (
            client.post(
                "/v1/session",
                json={"password": "wrong"},
                headers=headers(f"198.51.100.{i}", "fake"),
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/v1/session", json={"password": PASSWORD}, headers=headers("198.51.100.99", "fake")
        ).status_code
        == 401
    )


def test_expired_client_buckets_are_reclaimed(monkeypatch):
    from app.services import session

    monkeypatch.setattr(session, "monotonic", lambda: 1000)
    auth = DemoSessions(PASSWORD, origin="https://demo.example")
    auth._attempts.update({str(i): deque([0]) for i in range(1024)})
    assert auth.login(PASSWORD, "new-client") is not None
    assert len(auth._attempts) == 1
