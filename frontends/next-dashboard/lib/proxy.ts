import { NextRequest, NextResponse } from "next/server";

/**
 * Shared runtime proxy for forwarding requests to the backend API.
 *
 * Reads API_URL at request time (not build time), so Docker can set
 * it to the internal network address (e.g. http://companion_x-api:8000)
 * while local dev defaults to http://localhost:8000 (unified server).
 */
export function getApiUrl() {
  return process.env.API_URL || "http://localhost:8000";
}

export async function proxyRequest(
  req: NextRequest,
  path: string[],
  prefix: string,
): Promise<NextResponse> {
  const target = path.length > 0
    ? `${getApiUrl()}/${prefix}/${path.join("/")}`
    : `${getApiUrl()}/${prefix}`;
  return forwardTo(req, target);
}

/**
 * Proxy straight through to an exact upstream URL (no ``/prefix/path``
 * join). Used by the ``/mcp`` route — FastMCP's streamable-HTTP app is
 * mounted at ``/mcp/`` (trailing slash required, redirects otherwise) with
 * no sub-path segments, unlike ``/api/*`` and ``/ag-ui/*``.
 */
export async function proxyExact(req: NextRequest, targetUrl: string): Promise<NextResponse> {
  return forwardTo(req, targetUrl);
}

async function forwardTo(req: NextRequest, target: string): Promise<NextResponse> {
  const url = new URL(target);
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));

  const headers = new Headers(req.headers);
  headers.delete("host");

  const init: RequestInit = { method: req.method, headers };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  try {
    const upstream = await fetch(url.toString(), init);

    // For SSE streams, pipe through directly
    if (upstream.headers.get("content-type")?.includes("text/event-stream")) {
      return new NextResponse(upstream.body, {
        status: upstream.status,
        headers: Object.fromEntries(upstream.headers.entries()),
      });
    }

    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: upstream.status,
      headers: Object.fromEntries(upstream.headers.entries()),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Proxy error";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
