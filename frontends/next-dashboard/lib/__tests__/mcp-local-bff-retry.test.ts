// @vitest-environment node
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { proxyLocalMcp } from "../mcp-local-bff";
import { resetCredentialPreference } from "../mcp-local-credential-retry";

const STALE = "stale-env-token-0123456789";
const FRESH = "fresh-file-token-0123456789";
let dir: string;
let upstream: ReturnType<typeof vi.fn>;

function request(): NextRequest {
  return new NextRequest("http://localhost:13000/mcp", {
    method: "POST",
    headers: { host: "localhost:13000", origin: "http://localhost:13000", "content-type": "application/json", "x-companion-x-local": "1" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }),
  });
}
const bearer = (call: number): string => String(((upstream.mock.calls[call][1] as RequestInit).headers as Headers).get("authorization"));
const answer = (okToken: string) => async (_url: unknown, init: RequestInit) =>
  (init.headers as Headers).get("authorization") === `Bearer ${okToken}`
    ? new Response('{"ok":true}', { status: 200, headers: { "content-type": "application/json" } })
    : new Response('{"error":"invalid_token","error_description":"Authentication required"}', { status: 401, headers: { "content-type": "application/json" } });

beforeEach(() => {
  resetCredentialPreference();
  dir = mkdtempSync(path.join(tmpdir(), "mcp-token-"));
  const file = path.join(dir, "local-mcp-token");
  writeFileSync(file, FRESH);
  chmodSync(file, 0o600);
  process.env.MCP_LOCAL_AUTH = "true";
  process.env.MCP_LOCAL_TOKEN_FILE = file;
  process.env.MCP_LOCAL_AUTH_TOKEN = STALE;
  process.env.API_URL = "http://127.0.0.1:18000";
  upstream = vi.fn();
  vi.stubGlobal("fetch", upstream);
});
afterEach(() => {
  vi.unstubAllGlobals();
  rmSync(dir, { recursive: true, force: true });
  delete process.env.MCP_LOCAL_AUTH; delete process.env.MCP_LOCAL_TOKEN_FILE;
  delete process.env.MCP_LOCAL_AUTH_TOKEN; delete process.env.API_URL;
});

describe("local MCP proxy credential retry", () => {
  it("retries once with the launcher file when the ambient token is stale", async () => {
    upstream.mockImplementation(answer(FRESH));
    const res = await proxyLocalMcp(request());
    expect(res.status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(2);
    expect(bearer(0)).toBe(`Bearer ${STALE}`);
    expect(bearer(1)).toBe(`Bearer ${FRESH}`);
  });

  it("does not retry when the first credential works", async () => {
    upstream.mockImplementation(answer(STALE));
    expect((await proxyLocalMcp(request())).status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(1);
  });

  it("prefers the credential that last worked, so later calls do not pay for a retry", async () => {
    upstream.mockImplementation(answer(FRESH));
    await proxyLocalMcp(request());
    upstream.mockClear();
    expect((await proxyLocalMcp(request())).status).toBe(200);
    expect(upstream).toHaveBeenCalledTimes(1);
    expect(bearer(0)).toBe(`Bearer ${FRESH}`);
  });

  it("tells the user how to recover when every credential is rejected", async () => {
    upstream.mockImplementation(answer("something-else-entirely-0123"));
    const res = await proxyLocalMcp(request());
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBe("invalid_token");
    expect(body.error_description).toMatch(/restart the dashboard with scripts\/companion-x-ui\.sh/i);
  });

  it("does not retry the same token twice when env and file agree", async () => {
    process.env.MCP_LOCAL_AUTH_TOKEN = FRESH;
    upstream.mockImplementation(answer("nope-nope-nope-nope-0123"));
    await proxyLocalMcp(request());
    expect(upstream).toHaveBeenCalledTimes(1);
  });
});
