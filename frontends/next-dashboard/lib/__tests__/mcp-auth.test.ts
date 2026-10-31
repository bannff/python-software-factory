import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { NextRequest } from "next/server";
import { SdkErrorCode, SdkHttpError } from "@modelcontextprotocol/client";

import { proxyLocalApi, proxyLocalMcp } from "@/lib/mcp-local-bff";
import { localMcpAuthorization } from "@/lib/mcp-local-credential";
import {
  McpAuthenticationError, normalizeMcpConnectionError,
} from "@/lib/mcp-client";

const tokenDirs: string[] = [];

/** Write a launcher-style token file with the given mode and return its path. */
function tokenFile(mode: number, token: string): string {
  const dir = mkdtempSync(path.join(tmpdir(), "mcp-token-"));
  tokenDirs.push(dir);
  const file = path.join(dir, "local-mcp-token");
  writeFileSync(file, token, { mode });
  return file;
}

function request(headers: Record<string, string> = {}): NextRequest {
  return new NextRequest("http://localhost:3000/mcp", {
    method: "POST",
    headers: {
      host: "localhost:3000",
      origin: "http://localhost:3000",
      "sec-fetch-site": "same-origin",
      "content-type": "application/json",
      "x-companion-x-local": "1",
      ...headers,
    },
    body: "{}",
  });
}

beforeEach(() => {
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  for (const dir of tokenDirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

describe("local MCP credential BFF", () => {
  it("injects only the server token and never forwards browser authority", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "server-local-token-123456");
    vi.stubEnv("API_URL", "http://localhost:8000");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", {
        status: 200,
        headers: { "content-type": "application/json", "set-cookie": "secret=bad" },
      }),
    );

    const response = await proxyLocalMcp(request({
      authorization: "Bearer browser-attacker",
      cookie: "credential=attacker",
      forwarded: "host=attacker.example",
      "x-forwarded-host": "attacker.example",
    }));

    expect(response.status).toBe(200);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("authorization")).toBe("Bearer server-local-token-123456");
    expect(headers.get("cookie")).toBeNull();
    expect(headers.get("forwarded")).toBeNull();
    expect(headers.get("x-forwarded-host")).toBeNull();
    expect(init.redirect).toBe("manual");
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(response.headers.get("cache-control")).toContain("no-store");
  });

  it("rejects cross-origin and unguarded requests before the upstream", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "server-local-token-123456");
    const fetchMock = vi.spyOn(globalThis, "fetch");

    expect((await proxyLocalMcp(request({ origin: "https://attacker.example" }))).status)
      .toBe(403);
    expect((await proxyLocalMcp(request({ "x-companion-x-local": "" }))).status)
      .toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fails closed when local auth is disabled or unconfigured", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "false");
    expect((await proxyLocalMcp(request())).status).toBe(401);

    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", path.join(tmpdir(), "no-such-mcp-token-file"));
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "short");
    const unconfigured = await proxyLocalMcp(request());
    expect(unconfigured.status).toBe(401);
    expect(await unconfigured.json()).toEqual({
      detail: expect.stringContaining("MCP_LOCAL_AUTH_TOKEN"),
    });

    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "unsafe-token-with-newline\n1234");
    expect((await proxyLocalMcp(request())).status).toBe(401);
  });

  it("prefers the ambient token over the launcher-persisted file", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "ambient-local-token-123456");
    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", tokenFile(0o600, "persisted-local-token-123456"));
    vi.stubEnv("API_URL", "http://localhost:8000");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("ok"));

    expect((await proxyLocalMcp(request())).status).toBe(200);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer ambient-local-token-123456");
  });

  it("falls back to the launcher-persisted 0600 token when the environment is empty", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "");
    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", tokenFile(0o600, "persisted-local-token-123456"));
    vi.stubEnv("API_URL", "http://localhost:8000");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("ok"));

    expect((await proxyLocalMcp(request())).status).toBe(200);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer persisted-local-token-123456");
    expect(localMcpAuthorization()).toEqual({
      headers: { authorization: "Bearer persisted-local-token-123456" },
      missing: false,
    });
  });

  it("refuses a token file any other user could read", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "");
    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", tokenFile(0o644, "persisted-local-token-123456"));
    const fetchMock = vi.spyOn(globalThis, "fetch");

    expect((await proxyLocalMcp(request())).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses a symlinked token file and an oversized one", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "");

    const real = tokenFile(0o600, "persisted-local-token-123456");
    const link = path.join(path.dirname(real), "linked-mcp-token");
    symlinkSync(real, link);
    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", link);
    expect((await proxyLocalMcp(request())).status).toBe(401);

    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", tokenFile(0o600, "x".repeat(4096)));
    expect((await proxyLocalMcp(request())).status).toBe(401);
  });

  it("refuses a FIFO at the token path without blocking", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "");
    const dir = mkdtempSync(path.join(tmpdir(), "mcp-fifo-"));
    tokenDirs.push(dir);
    const fifo = path.join(dir, "local-mcp-token");
    execFileSync("mkfifo", ["-m", "600", fifo]);

    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", fifo);
    const started = Date.now();
    expect((await proxyLocalMcp(request())).status).toBe(401);
    expect(Date.now() - started).toBeLessThan(1000);
  });

  it("does not disclose the token-file path in the client-visible 401", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "");
    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", path.join(tmpdir(), "no-such-mcp-token-file"));

    const response = await proxyLocalMcp(request());
    expect(response.status).toBe(401);
    const body = await response.text();
    expect(body).toContain("MCP_LOCAL_AUTH_TOKEN");
    expect(body).not.toContain("no-such-mcp-token-file");
  });

  it("admits IPv6 loopback", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "server-local-token-123456");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("ok"));
    const ipv6 = new NextRequest("http://[::1]:3000/mcp", {
      method: "POST",
      headers: {
        host: "[::1]:3000", origin: "http://[::1]:3000",
        "sec-fetch-site": "same-origin", "content-type": "application/json",
        "x-companion-x-local": "1",
      },
      body: "{}",
    });
    expect((await proxyLocalMcp(ipv6)).status).toBe(200);
  });

  it("admits only an exact owner-scoped Terminal completion path", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "server-local-token-123456");
    vi.stubEnv("API_URL", "http://localhost:8000");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    const session = `term_${"a".repeat(32)}`;
    expect((await proxyLocalApi(request(), `/api/terminal/sessions/${session}/complete`)).status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
    expect((await proxyLocalApi(request(), "/api/terminal/sessions/not-a-session/complete")).status).toBe(404);
  });

  it("maps version-probe authentication failures to an actionable error", () => {
    const sdkError = new SdkHttpError(
      SdkErrorCode.ClientHttpAuthentication,
      "Version negotiation failed: HTTP 401",
      { status: 401, statusText: "Unauthorized", text: "" },
    );
    const normalized = normalizeMcpConnectionError(sdkError);
    expect(normalized).toBeInstanceOf(McpAuthenticationError);
    expect((normalized as McpAuthenticationError).message).toContain("/mcp");
    const other = new Error("offline");
    expect(normalizeMcpConnectionError(other)).toBe(other);
  });

  it("rejects credentialed redirects and hides upstream topology", async () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "server-local-token-123456");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 307, headers: { location: "http://attacker/" } }),
    );
    const response = await proxyLocalMcp(request());
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("attacker");
  });

  it("projects the validated server token into server-side AG-UI only", () => {
    vi.stubEnv("MCP_LOCAL_AUTH", "true");
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "server-local-token-123456");
    expect(localMcpAuthorization()).toEqual({
      headers: { authorization: "Bearer server-local-token-123456" },
      missing: false,
    });

    vi.stubEnv("MCP_LOCAL_TOKEN_FILE", path.join(tmpdir(), "no-such-mcp-token-file"));
    vi.stubEnv("MCP_LOCAL_AUTH_TOKEN", "short");
    expect(localMcpAuthorization()).toEqual({ headers: {}, missing: true });

    vi.stubEnv("MCP_LOCAL_AUTH", "false");
    expect(localMcpAuthorization()).toEqual({ headers: {}, missing: false });
  });
});
