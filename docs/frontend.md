# Ryuk frontend integration

Ryuk is the visible product name. The original planning documents and internal
AgentPay identifiers remain intact. The UI uses off-black paper, restrained red,
serif headings, monospace records, thin borders, original line-art mountains and
subtle grain. It contains no franchise logos, character art, generic AI gradients
or fabricated financial verdicts.

## Start your private demo

Keep your existing root `.env` private; **do not upload or commit it**. Compare it
with `.env.example` and add missing settings rather than overwriting your file.

For a local HTTP demo at exactly `http://localhost:3000`, configure:

- `RYUK_DEMO_ENABLED=true`
- `RYUK_DEMO_PASSWORD`: your own password of at least 16 characters; no default exists.
- `RYUK_APP_ORIGIN=http://localhost:3000`
- `RYUK_SECURE_COOKIES=false` **for local HTTP only**; use true with HTTPS.
- `LLM_PROVIDER=groq`, private `GROQ_API_KEY` and `GROQ_MODEL=openai/gpt-oss-120b`; alternatively select `openai` and set `OPENAI_API_KEY`/`OPENAI_MODEL`.
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `PAYPAL_MERCHANT_ID` from the
  supported Sandbox seller/app. Merchant ID is not the app client ID or a fictional
  fixture merchant ID. Use a separate Sandbox buyer account in the PayPal popup.

Then run from the repository root:

```sh
docker compose --env-file .env up --build -d --wait
```

Open `http://localhost:3000` and unlock the workspace using your demo password.
The exact origin matters; changing to an IP address/port requires matching origin
configuration. PayPal Sandbox credentials do not move real funds or book a hotel.

Compose keeps private credentials on the backend and gives Next only the internal
`RYUK_BACKEND_URL=http://backend:8000`. The checkout database uses the persistent
`checkout_data` volume under a private non-root-owned `/app/data` directory.
The initial backend account is USD 1,500 with a USD 1,500 per-purchase hard ceiling
and USD 1,300 review threshold. These are trusted backend policy values, not model
or browser settings. Existing spending/reservations are preserved across restart;
startup never resets the ledger or creates new funds. Changing `.env` seed budget
does not overwrite an existing account. Do not reset an uncertain payment ledger.

Health and catalog work with demo mode off. Private routes remain unavailable
until explicitly configured. With demo mode on, missing selected-provider credentials give a
safe parsing error; missing PayPal credentials/mapping leaves checkout visibly
unavailable. There is no fake runtime parser, fake buyer approval or fake payment
fallback. The original `NEXT_PUBLIC_*` template variables remain for compatibility;
the UI uses the same-origin proxy and receives only the public PayPal client ID
from authenticated backend configuration. It never receives the client secret.

For Python/Next development, export backend settings into the backend process
without committing them, set a private local `RYUK_CHECKOUT_DB_PATH`, run Uvicorn
with one worker, and run `npm run dev` in `frontend`. Set server-only
`RYUK_BACKEND_URL` if the backend is not at `http://127.0.0.1:8000`.
Neither Python nor Next implicitly loads a root `.env` for both services; Compose
is the simplest way to use the root file. See README for dependency setup.

## Flow and ownership

`POST /v1/requests` accepts only the natural-language query. It calls the existing
parser interface, stores canonical proposals from the trusted catalog, reruns the
existing verifier/policy, and returns typed intent, candidates, exact evidence and
policy outcomes. The first three candidate records show the planned eligible,
review and denied examples; remaining backend records expand on demand. This is
stable catalog order, not a fabricated LLM ranking. Required evidence counts and
preference percentages come from backend verification and are labeled separately.

Selecting a record reloads its backend state. Application review uses the existing
approval service through request/decision endpoints. The modal shows exact bound
merchant, integer-money display/currency, available budget, evidence status,
escalation codes and expiry. Rejection does not create checkout. Hard DENY has no
checkout button, and the backend independently rejects direct attempts.

The PayPal JavaScript **v5 Buttons** API loads directly from PayPal. Official references: [Buttons](https://developer.paypal.com/sdk/js/v5/reference/) and [script configuration](https://developer.paypal.com/sdk/js/v5/configuration). `createOrder`
posts only the proposal ID to the existing backend checkout API and returns the
backend order ID. The SDK never receives browser-supplied amount/merchant for
order creation. `onApprove` requests backend capture by internal checkout ID with
an empty action body. It does not mark success, call `actions.order.capture`, or
trust a browser-supplied provider order ID. Only backend SUCCEEDED displays payment
confirmation; capture reference, snapshot, provider status and remaining budget
come from backend records. Pending outcomes retain their reservation and offer a
status check that reconciles without recapture. Candidate switching is locked
while an order/dispatch is active, and old SDK components are closed on unmount.

The audit timeline combines real backend proposal/verification/policy/approval
records with persisted checkout events, using backend timestamps. No UI-generated
financial events or invented delay/timestamps are displayed. Canonical proposals/approvals, early audit and checkout state/keys/terms/reservations now persist in SQLite. Sign in again after restart and use Saved activity to inspect or reconcile existing purchases without recapture. Pre-upgrade missing canonical records remain unavailable for new capture; see [durable recovery](durable-authority.md).

### Step 12 security change: intent review is always required

All model-derived candidates require application review, including otherwise
below-threshold eligible offers. The review dialog shows original instruction,
parsed mandatory/preferred values, quantity and requested money limits. Reject
omissions or changed meaning. Approval binds the backend review flag and the
intent-bearing snapshot using proposal digest v2; current policy and consent still
revalidate before capture. This does not establish complete model semantic fidelity.
See [security review](security-review.md) and D-033.

## Authentication and proxy boundary

This is an explicitly enabled **single-buyer private Sandbox demo**, not a
production multi-user identity system. Login verifies a backend-only password
with scrypt/constant-time comparison and limits attempts to five per client per
minute. A random opaque token is stored only as a hash server-side; the browser
receives a 20-minute HttpOnly, SameSite=Strict cookie. Logout revokes it. Server
restart invalidates sessions. No browser user-ID header chooses financial identity.

A Next server route proxies an allowlist of API paths, forwards cookies and the
actual request origin, disables caching/redirects, bounds request size and sanitizes
backend failures. Mutating requests must have the same browser host; the backend
also requires the exact configured origin. Credentials never enter browser build
configuration. API ownership checks and pre-capture authorization remain in the
existing services. No financial policy is evaluated in TypeScript.

Production authentication and multi-worker durable canonical authority remain
separate work. Step 12's source/mock review is recorded in `security-review.md`;
remaining Medium/Low risks are not production acceptance. HTTPS now rejects
insecure-cookie configuration at startup. Validation errors contain no submitted
values. Direct parser HTTP calls require private authentication before provider setup.

## Tests

```sh
cd backend
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/python -m pip check

cd ../frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

The committed browser suite uses a **test-only** FastAPI server with the real
services/SQLite and mocked OpenAI extraction/PayPal transport. Its new-case/approval
  hooks are defined only in `backend/tests/frontend_server.py`, never imported by
production startup and excluded from the backend Docker build. The SDK is
intercepted only by the browser test. It is not a demo-mode financial fallback.
Every new case allocates a fresh uniquely named temporary ledger; no existing
reservations/checkouts/spending are deleted or reset. `RYUK_E2E_ROOT` chooses only
the temporary parent directory, never an existing database file.

Run in separate terminals from repository root:

```sh
# Test fixtures only; no live credentials are read for these provider calls.
PYTHONPATH=backend:backend/tests \
  backend/.venv/bin/python backend/tests/frontend_server.py

# A dedicated Next instance; stop any instance using the same .next directory.
cd frontend
RYUK_BACKEND_URL=http://127.0.0.1:8100 npm run dev -- --port 3100

# From frontend, Chromium must be installed (or set CHROMIUM_PATH).
npm run test:e2e
```

Historical Step 11 evidence: 962 backend cases including 16 new session/workspace cases;
ESLint, TypeScript, production build; 13 Chromium assertions over the actual
Next proxy/FastAPI flow at desktop and mobile sizes, with no page runtime errors
or horizontal overflow. The production browser suite took 14.6 seconds for all
mocked scenarios, including review/reject/eligible/timeout recovery. This is not
an assertion about live model latency or PayPal buyer-login timing. Compose config,
private credential isolation and static-browser-bundle secret-marker checks pass.
Images were not rebuilt in this stage; local production frontend and backend were
used for browser validation. `next start` emits the existing standalone-output
advisory; Docker uses its intended standalone server entrypoint.

## Live acceptance and next stage

**Step 11 is not accepted as complete yet.** The shared checkout/environment did
not contain the user's local `.env` or configured provider credentials. No live
model request or real Sandbox buyer transaction was made. The actual SDK integration
is implemented, but its popup/account/capture acceptance remains unverified.

Before closing Step 11, run the real parser and Sandbox buyer flow using private
configuration, verify the final provider capture/reference/ledger/audit, and time
the live happy path under three minutes. Do not substitute the browser test hook.
Step 12 was subsequently requested and performed on the current source without live
provider calls. That review does not close Step 11 live acceptance or certify the demo.

## Changed files in this stage

- `.env.example`, `docker-compose.yml`, `backend/Dockerfile`
- `backend/app/main.py`, `backend/app/api/checkout.py`, `backend/app/api/workspace.py`
- `backend/app/services/session.py`, `backend/app/services/provisioning.py`, `backend/app/services/workspace.py`
- `backend/tests/test_workspace.py`, `backend/tests/frontend_server.py`
- `frontend/app/page.tsx`, `frontend/app/globals.css`, `frontend/app/layout.tsx`
- `frontend/app/api/ryuk/[...path]/route.ts`, `frontend/components/paypal.tsx`
- `frontend/lib/api.ts`, `frontend/lib/contracts.ts`, `frontend/tests/e2e.mjs`
- `frontend/package.json`, `frontend/package-lock.json`
- `README.md`, `ARCHITECTURE.md`, `TASKS.md`, `STATUS.md`, `DECISIONS.md`
- `docs/frontend.md`, `docs/demo-script.md`, `docs/checkout.md`

## Startup failure: backend exited (3)

The original generic `Invalid private Ryuk demo configuration` error did not
identify the failing input. The updated build reports only the setting name and
expected format; private values and raw exception contents stay omitted.

```sh
git pull origin main
docker compose --env-file .env up --build -d --wait
docker compose logs --no-color --tail=30 backend
```

Check the named setting locally. Passwords require at least 16 characters; origins
must be complete HTTPS origins or HTTP localhost/127.0.0.1/[::1] origins, without
paths/credentials; cookie flags are true/false; seed budget uses integer minor
units; merchant ID is the actual Sandbox seller ID, not an email or secret.
A database error identifies the private SQLite directory/volume for inspection.
The new diagnostics do not prove the cause on a user's device until that device
runs the updated image. Share only the sanitized final error, never `.env`.

## Security-review update
All model-derived candidates now require review even below threshold. Compare the original request and full parsed intent in the exact-terms dialog, then approve/reject the digest-bound proposal. This is separate from PayPal buyer approval and does not prove semantic completeness. HTTPS deployments must enable secure cookies. The test-only server now requires RYUK_E2E_TEST_ONLY=1 and always uses fresh temporary storage; see operations.md for commands. Production/model credentials must never be supplied to the fixture server. Current evidence and remaining acceptance gates are in STATUS.md.

## PayPal popup spinning with HTTP 200
HTTP 200 is transport success, not necessarily payment SUCCEEDED. Read the existing checkout response/backend record before attempting another payment. A fixed SDK lifecycle bug previously closed/unmounted the button while onApprove was still resolving; the component now stays mounted through the callback. Pull the fix and rebuild/recreate **frontend only** (`docker compose up -d --build --force-recreate --no-deps frontend`). Avoid restarting the backend or clearing its ledger to troubleshoot a popup. Never repeat capture for CAPTURE_PENDING/PENDING_PROVIDER; use the existing check/reconcile action. The user's live browser/provider outcome remains an acceptance check, not established by mocked tests.

## Proxy-aware login configuration
Compose now includes a trusted ingress and requires a private RYUK_PROXY_SHARED_SECRET (32–256 random ASCII characters) for browser login. Add it locally to .env before upgrading; recreate backend, frontend and ingress together. Frontend port 3000 is not directly published. See [login rate-limit trust boundary](login-rate-limits.md).

## Requirement source links
New parser responses retain validated requirement_sources associations. Original text is shown beside mandatory/preferred lists, with exact source quotes and keyboard links. Older quote-less records explicitly indicate missing source text; no quote is inferred. Provenance is bound with the full intent snapshot/digest and does not prove semantic completeness or grant spend authority. See [contract and compatibility](intent-provenance.md).
