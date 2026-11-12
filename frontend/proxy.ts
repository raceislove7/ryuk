import { randomBytes } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  const nonce = randomBytes(24).toString("base64");
  const development = process.env.NODE_ENV === "development";
  const paypal = "https://*.paypal.com https://*.paypalobjects.com";
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' ${paypal}${development ? " 'unsafe-eval'" : ""}`,
    "script-src-attr 'none'",
    // Next/PayPal create dynamic style attributes. Script nonces remain strict.
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: ${paypal}`,
    "font-src 'self'",
    `connect-src 'self' ${paypal}${development ? " ws: wss:" : ""}`,
    `frame-src 'self' ${paypal}`,
    "worker-src 'self' blob:",
    `form-action 'self' ${paypal}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
  ].join("; ");
  const headers = new Headers(request.headers);
  // Never accept a caller-selected nonce or CSP. Next reads this CSP for SSR scripts.
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = {
  matcher: ["/((?!api/|_next/static|_next/image|favicon.ico).*)"],
};
