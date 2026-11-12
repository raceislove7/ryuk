import { isIP } from "node:net";
import { NextRequest } from "next/server";

export const runtime = "nodejs";
const allowed =
  /^(session|workspace|history|requests|proposals\/[a-zA-Z0-9_-]+(?:\/(select|approval|audit))?|approvals\/[a-zA-Z0-9_-]+\/decision|checkouts(?:\/[a-zA-Z0-9_-]+(?:\/(capture|reconcile|cancel))?)?)$/;

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const path = (await context.params).path.join("/");
  if (!allowed.test(path))
    return Response.json({ detail: "Not found" }, { status: 404 });
  let sameOrigin = false;
  try {
    sameOrigin =
      new URL(request.headers.get("origin") || "").host ===
      request.headers.get("host");
  } catch {}
  if (!["GET", "HEAD"].includes(request.method) && !sameOrigin) {
    return Response.json(
      { detail: "Request origin is not allowed" },
      { status: 403 },
    );
  }
  const proxyHeaders: Record<string, string> = {};
  const secret = process.env.RYUK_PROXY_SHARED_SECRET || "";
  if (process.env.RYUK_TRUST_INGRESS === "true") {
    const address = request.headers.get("x-ryuk-client-ip") || "";
    if (path === "session" && request.method === "POST" &&
        (secret.length < 32 || secret.length > 256 || !isIP(address)))
      return Response.json({ detail: "Trusted login proxy is not configured" }, { status: 503 });
    if (secret.length >= 32 && secret.length <= 256 && isIP(address)) {
      proxyHeaders["X-Ryuk-Client-IP"] = address;
      proxyHeaders["X-Ryuk-Proxy-Token"] = secret;
    }
  }
  let body: string | undefined;
  if (!["GET", "HEAD"].includes(request.method) && request.body) {
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const item = await reader.read();
      if (item.done) break;
      size += item.value.byteLength;
      if (size > 65_536) {
        await reader.cancel();
        return Response.json({ detail: "Request too large" }, { status: 413 });
      }
      chunks.push(item.value);
    }
    body = Buffer.concat(chunks).toString("utf8");
  }
  try {
    const upstream = await fetch(
      `${process.env.RYUK_BACKEND_URL || "http://127.0.0.1:8000"}/v1/${path}${path === "history" ? request.nextUrl.search : ""}`,
      {
        method: request.method,
        body,
        redirect: "manual",
        cache: "no-store",
        signal: AbortSignal.timeout(35_000),
        headers: {
          ...proxyHeaders,
          "Content-Type": "application/json",
          Cookie: request.headers.get("cookie") || "",
          Origin: request.headers.get("origin") || "",
        },
      },
    );
    const headers = new Headers({
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      Vary: "Cookie",
    });
    for (const cookie of upstream.headers.getSetCookie())
      headers.append("Set-Cookie", cookie);
    if (upstream.status >= 300 && upstream.status < 400)
      return Response.json({ detail: "Backend unavailable" }, { status: 502 });
    const text = await upstream.text();
    try {
      JSON.parse(text);
    } catch {
      return Response.json(
        { detail: "Backend unavailable; please check the recorded state." },
        { status: 502 },
      );
    }
    return new Response(text, {
      status: upstream.status,
      headers,
    });
  } catch {
    return Response.json(
      { detail: "The private workspace is unavailable. Please try again." },
      { status: 503 },
    );
  }
}
export { proxy as GET, proxy as POST, proxy as DELETE };
