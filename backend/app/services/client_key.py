"""Authenticate a client-address assertion from the private frontend proxy."""

import hmac
from ipaddress import ip_address

from fastapi import Request


def login_client_key(request: Request, proxy_secret: str | None) -> str:
    """Ignore all forwarded identity unless the backend proxy channel authenticates it."""
    peer = request.client.host if request.client else "unknown"
    if proxy_secret:
        token = request.headers.get("x-ryuk-proxy-token", "")
        address = request.headers.get("x-ryuk-client-ip", "")
        if len(token) <= 256 and hmac.compare_digest(token.encode(), proxy_secret.encode()):
            try:
                ip = ip_address(address)
                if getattr(ip, "ipv4_mapped", None):
                    ip = ip.ipv4_mapped
                return "proxy:" + str(ip)
            except ValueError:
                pass
    return "peer:" + peer
