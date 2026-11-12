# Nonce-based script policy

The Next proxy creates 24 random bytes for every document response, overwrites incoming x-nonce/CSP headers, and supplies the resulting CSP to both Next's request rendering and the browser response. The async root layout reads that nonce, making HTML dynamic. Private/no-store prevents nonce-bearing HTML from being shared between requests. Do not add shared edge HTML caching or override this header downstream.

Production script-src contains a nonce and strict-dynamic, with self/PayPal/PayPalObjects host fallbacks for older browsers. There is no production unsafe-inline or unsafe-eval for scripts. Inline event-handler attributes are blocked separately by script-src-attr 'none'. Only development adds unsafe-eval and WebSocket connections for Next tooling; do not run the dev server as the production deployment.

Next automatically applies the request-CSP nonce to its rendered scripts. The PayPal loader sets both script.nonce and data-csp-nonce from the document nonce so the SDK can propagate it to generated content. Missing nonce fails checkout loading closed. Keep the dynamic root layout and request/response CSP in sync; a static prerendered page cannot safely reuse a per-request nonce.

The policy also restricts default sources, object/base/framing/form actions, connections, fonts, images, workers and child frames. PayPal/PayPalObjects subdomains are explicitly permitted for payment assets, frames and connections. Style-src retains unsafe-inline for React/PayPal dynamic styles; this does not permit inline JavaScript. Strict-dynamic delegates descendant script loading to nonce-trusted code in supporting browsers; host lists are compatibility fallbacks, not an assertion that a compromised trusted SDK cannot load descendants.

## Validation and limits

Production-browser regressions verify unique nonces across requests, ignored caller nonce/CSP, no-store, Next SSR nonce inclusion and both PayPal nonce attributes. With the actual response policy, parser-inserted inline scripts, event handlers and an untrusted external script are blocked; CSP violation events are observed. The existing mocked SDK purchase, pending/cancel, recovery and mobile flows still pass.

Those tests replace the SDK with a controlled mock; they do not certify every live PayPal SDK branch or a future SDK change. Recheck the real Sandbox buyer flow after deploying. If provider assets are blocked, inspect the exact CSP violation and document a narrowly justified change; do not add unsafe-inline/eval to production scripts or wildcard all sources. A trusted third-party script can still act in the page; CSP does not replace escaping, dependency review, HttpOnly cookies or backend financial authorization. No new payment was made to validate this change.

The JSON proxy/API and static assets are outside document-nonce middleware; they keep their existing content type, no-cache/security controls. This document policy applies to rendered pages, where scripts execute.

## Rollout

No secret/configuration addition is required. Pull the new revision and rebuild the frontend; recreate ingress if your previous deployment does not yet include it. Preserve the backend/ledger and active purchase context:

```sh
docker compose up -d --build --wait --no-deps frontend
```

Check the document response's CSP and the browser console, then verify a freshly loaded page unlocks and mounts the PayPal button. Keep the existing no-blind-recapture policy for any already pending payment. Release tags remain unchanged until an explicitly requested new freeze.
