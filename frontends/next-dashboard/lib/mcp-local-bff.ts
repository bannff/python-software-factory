import { NextRequest, NextResponse } from "next/server";

import {
  localMcpAuthEnabled,
  localTokenFileDisplayPath,
  resolveLocalCredential,
} from "./mcp-local-credential";

const LOCAL_HOSTS = new Set([
  "127.0.0.1", "::1", "localhost",
]);
const UPSTREAM_HOSTS = new Set([
  ...LOCAL_HOSTS, "companion_x-api", "host.docker.internal",
]);
const REQUEST_HEADERS = [
  "accept", "content-type", "last-event-id",
  "mcp-protocol-version", "mcp-session-id",
];
const RESPONSE_HEADERS = [
  "content-type", "mcp-protocol-version", "mcp-session-id",
  "retry-after", "www-authenticate",
];
const MAX_REQUEST_BYTES = 1_048_576;
const LOCAL_GUARD = "x-companion-x-local";

// Localhost development trusts processes running as the same OS user. The
// Host/Origin/Fetch-Metadata/custom-header checks prevent an internet origin
// from turning the loopback BFF into a browser confused deputy; this is not a
// hosted multi-user session boundary.

/** Project the explicit local bearer without exposing it to browser JavaScript. */
export async function proxyLocalMcp(req: NextRequest): Promise<NextResponse> {
  return proxyLocalApi(req, "/mcp/");
}

/** Proxy one allowlisted local API path with the same confused-deputy guard. */
export async function proxyLocalApi(
  req: NextRequest, pathname: string,
): Promise<NextResponse> {
  if (!pathname.startsWith("/mcp/")
      && !/^\/api\/terminal\/(sessions(?:\/term_[0-9a-f]{32}(?:\/(?:attach|complete))?)?|shells)$/.test(pathname)) {
    return failure(404, "Local API route is not allowed");
  }
  const admission = admitLocalRequest(req);
  if (admission) return admission;

  const config = localConfig();
  if (config instanceof NextResponse) return config;

  const length = Number(req.headers.get("content-length") ?? "0");
  if (!Number.isFinite(length) || length > MAX_REQUEST_BYTES) {
    return failure(413, "Local request is too large");
  }
  const body = req.method === "GET" ? undefined : await req.text();
  if (body && new TextEncoder().encode(body).byteLength > MAX_REQUEST_BYTES) {
    return failure(413, "Local request is too large");
  }

  try {
    const target = new URL(pathname, config.apiUrl);
    target.search = req.nextUrl.search;
    const headers = selectedHeaders(req.headers, REQUEST_HEADERS);
    headers.set("authorization", `Bearer ${config.token}`);
    const upstream = await fetch(target, {
      method: req.method, headers, body, cache: "no-store",
      redirect: "manual", signal: req.signal,
    });
    if (upstream.status >= 300 && upstream.status < 400) {
      return failure(502, "Local upstream redirect rejected");
    }
    const responseHeaders = selectedHeaders(upstream.headers, RESPONSE_HEADERS);
    responseHeaders.set("cache-control", "private, no-store, max-age=0");
    return new NextResponse(upstream.body, {
      status: upstream.status, headers: responseHeaders,
    });
  } catch {
    return failure(502, "Local backend is unavailable");
  }
}

function admitLocalRequest(req: NextRequest): NextResponse | null {
  if (!["GET", "POST", "DELETE"].includes(req.method)) {
    return failure(405, "MCP method is not allowed");
  }
  const host = req.headers.get("host") ?? "";
  if (!LOCAL_HOSTS.has(parseHostname(host))) {
    return failure(403, "Local MCP requires a loopback host");
  }
  if (req.headers.get(LOCAL_GUARD) !== "1") {
    return failure(403, "Local MCP request guard is missing");
  }
  const fetchSite = req.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin") {
    return failure(403, "Cross-site MCP requests are forbidden");
  }
  const origin = req.headers.get("origin");
  if (origin && !sameOrigin(origin, host)) {
    return failure(403, "Cross-origin MCP requests are forbidden");
  }
  if (req.method !== "GET" && !origin) {
    return failure(403, "MCP mutation requires an Origin header");
  }
  if (req.method === "POST") {
    const contentType = req.headers.get("content-type") ?? "";
    if (!contentType.toLowerCase().startsWith("application/json")) {
      return failure(415, "MCP requires application/json");
    }
  }
  return null;
}

function localConfig(): { apiUrl: URL; token: string } | NextResponse {
  if (!localMcpAuthEnabled()) {
    return failure(401, "Local MCP authentication is disabled");
  }
  const credential = resolveLocalCredential();
  if (credential === null) {
    logMissingCredentialOnce();
    return failure(
      401,
      "Local MCP authentication is not configured (checked MCP_LOCAL_AUTH_TOKEN and the launcher token file)",
    );
  }
  try {
    const apiUrl = new URL(process.env.API_URL || "http://localhost:8000");
    if (apiUrl.protocol !== "http:" || !UPSTREAM_HOSTS.has(apiUrl.hostname)
        || apiUrl.username || apiUrl.password || apiUrl.search || apiUrl.hash) {
      return failure(503, "Local MCP upstream is not allowed");
    }
    return { apiUrl, token: credential.token };
  } catch {
    return failure(503, "Local MCP upstream is invalid");
  }
}

function selectedHeaders(source: Headers, names: string[]): Headers {
  const selected = new Headers();
  for (const name of names) {
    const value = source.get(name);
    if (value !== null) selected.set(name, value);
  }
  return selected;
}

function parseHostname(host: string): string {
  try {
    const hostname = new URL(`http://${host}`).hostname;
    return hostname.startsWith("[") && hostname.endsWith("]")
      ? hostname.slice(1, -1) : hostname;
  } catch { return ""; }
}

let missingCredentialLogged = false;

/** One explicit line naming the cause, instead of only repeated generic 401s. */
function logMissingCredentialOnce(): void {
  if (missingCredentialLogged) return;
  missingCredentialLogged = true;
  console.warn(
    "[mcp-local-bff] Local MCP authentication is not configured: set "
    + "MCP_LOCAL_AUTH_TOKEN or start Companion X with scripts/companion-x-ui.sh "
    + `(token file: ${localTokenFileDisplayPath()}).`,
  );
}

function sameOrigin(candidate: string, expectedHost: string): boolean {
  try {
    const origin = new URL(candidate);
    return origin.protocol === "http:" && origin.host === expectedHost;
  } catch { return false; }
}

function failure(status: number, detail: string): NextResponse {
  return NextResponse.json(
    { detail },
    { status, headers: { "cache-control": "private, no-store, max-age=0" } },
  );
}
