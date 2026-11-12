# Login client identity behind the proxy

Compose now publishes ingress on localhost:3000; the frontend has no published port. Nginx overwrites incoming client-identity headers with its socket peer address. Next trusts that header only with RYUK_TRUST_INGRESS=true, and sends a backend-only RYUK_PROXY_SHARED_SECRET token with the address. The backend constant-time verifies that token before accepting a syntactically valid, normalized IPv4/IPv6 address as the rate-limit key. Headers never select a financial actor.

Browser-supplied Forwarded, X-Forwarded-For, X-Real-IP and proxy-token headers are not forwarded as authority. Missing/wrong authentication or malformed addresses use the direct peer's bucket, in a separate namespace from verified proxy clients. Uvicorn's proxy-header processing is disabled in the backend image so a direct caller cannot alter that peer through forwarded headers. Standalone development must likewise run Uvicorn with --no-proxy-headers. Next without trusted ingress ignores client-address assertions.

## Configure and upgrade

Add a unique random ASCII RYUK_PROXY_SHARED_SECRET (32–256 characters) to the ignored root .env; use a password manager and do not paste it into chat. The same backend-only value is passed to backend and frontend. It must never use NEXT_PUBLIC, be included in source, be logged or exposed to the browser. Rotate by updating both services together. Compose login fails closed with a safe 503 when this channel is missing/misconfigured; health/catalog can still start without it.

After preserving active purchases and backing up the ledger, recreate all three services:

```sh
docker compose --env-file .env up -d --build --wait backend frontend ingress
docker compose ps
```

Open exactly the configured origin (locally http://localhost:3000). Do not publish the frontend port or let untrusted workloads share the private application network. Only the trusted ingress may reach the frontend in this mode. Direct backend access stays loopback-only; trusted server operators and holders of the shared proxy secret are inside the trust boundary. Ordinary session/PayPal credentials are separate.

If another reverse proxy sits in front of Nginx, it is the socket peer and will share a bucket unless you deliberately configure Nginx's real-IP module with exact trusted source networks and a header that the outer ingress overwrites. Never enable broad trust in arbitrary incoming X-Forwarded-For or publish a frontend behind an unreviewed header-preserving proxy. NAT users still share an IP budget.

## Limiter behavior and limits

Five attempts per normalized client IP per rolling minute, successful or unsuccessful; changing browser-supplied IP strings cannot evade this. Inactive buckets are reclaimed before the 1,024-client capacity check. Active entries are not evicted to give attackers fresh allowances. Sessions and limits remain process-local for this private demo; multiple workers or instances need a shared limiter and reviewed ingress/global resource controls. Per-IP limits do not prevent distributed traffic, NAT collateral effects or an attacker with trusted network/secret access. Shared model-request allowance remains separate.

Validation covers distinct authenticated clients behind one proxy, spoofed/invalid headers, equivalent IP normalization and expired bucket reclamation. Docker ingress checks verify that forged headers cannot rotate a real socket's allowance and a second socket identity can still sign in.
