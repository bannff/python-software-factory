import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/mcp-client", () => ({ getMcpClient: async () => ({ callTool: mocks.callTool }) }));

import { enableConnectionBrick, listConnectionBricks } from "../connections-api";

const answer = (data: unknown) => ({ structuredContent: { ok: true, data } });

beforeEach(() => mocks.callTool.mockReset());

describe("Connections progressive MCP adapter", () => {
  it("normalizes registered and loaded bricks", async () => {
    mocks.callTool.mockResolvedValue(answer({ bricks: [
      { name: "agent", namespace: "factory.agent", tools_count: 12, loaded: true, healthy: true, error: null },
      { name: "browser", namespace: "factory.browser", tools_count: -1, loaded: false, healthy: true, error: null },
    ] }));
    await expect(listConnectionBricks()).resolves.toEqual([
      { name: "agent", namespace: "factory.agent", toolsCount: 12, loaded: true, healthy: true, error: null },
      { name: "browser", namespace: "factory.browser", toolsCount: -1, loaded: false, healthy: true, error: null },
    ]);
    expect(mocks.callTool).toHaveBeenCalledWith({ name: "list_bricks", arguments: {} });
  });

  it("loads one brick and returns its admitted tools", async () => {
    mocks.callTool.mockResolvedValue(answer({ brick: "browser", count: 1, tools: [
      { name: "browser_launch", description: "Launch", category: "operational" },
    ], invalid_tools: [] }));
    await expect(enableConnectionBrick("browser")).resolves.toEqual([
      { name: "browser_launch", description: "Launch", category: "operational" },
    ]);
    expect(mocks.callTool).toHaveBeenCalledWith({
      name: "get_brick_tools", arguments: { brick_name: "browser" },
    });
  });

  it("rejects malformed typed responses", async () => {
    mocks.callTool.mockResolvedValue({ structuredContent: { ok: false, error: "denied" } });
    await expect(listConnectionBricks()).rejects.toThrow("denied");
  });
});
