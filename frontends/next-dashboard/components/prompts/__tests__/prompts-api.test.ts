import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/mcp-client", () => ({
  getMcpClient: async () => ({ callTool: mocks.callTool }),
}));

import { listFactoryPrompts, renderFactoryPrompt, type FactoryPrompt } from "../prompts-api";

const result = (data: unknown) => ({ structuredContent: { ok: true, data } });

beforeEach(() => { mocks.callTool.mockReset(); });

describe("Prompts MCP API", () => {
  it("discovers and sorts prompts across registered bricks", async () => {
    mocks.callTool.mockImplementation(async ({ name, arguments: args }) => {
      if (name === "list_bricks") return result({ bricks: [
        { name: "ui", healthy: true }, { name: "agent", healthy: true },
        { name: "broken", healthy: false },
      ] });
      return result({ brick: args.brick_name, prompts: [{
        name: args.brick_name === "ui" ? "dashboard" : "reason",
        description: "Reusable guidance",
        arguments: [{ name: "task", description: "Work item", required: true }],
      }] });
    });
    await expect(listFactoryPrompts()).resolves.toEqual({ failedBricks: [], prompts: [
      { brick: "agent", name: "reason", description: "Reusable guidance", arguments: [
        { name: "task", description: "Work item", required: true },
      ] },
      { brick: "ui", name: "dashboard", description: "Reusable guidance", arguments: [
        { name: "task", description: "Work item", required: true },
      ] },
    ] });
    expect(mocks.callTool).not.toHaveBeenCalledWith(expect.objectContaining({
      arguments: { brick_name: "broken" },
    }));
  });

  it("retains healthy results and reports registries that fail", async () => {
    mocks.callTool.mockImplementation(async ({ name, arguments: args }) => {
      if (name === "list_bricks") return result({ bricks: [
        { name: "agent", healthy: true }, { name: "ui", healthy: true },
      ] });
      if (args.brick_name === "ui") throw new Error("load failed");
      return result({ prompts: [{ name: "reason", description: "Think", arguments: [] }] });
    });
    await expect(listFactoryPrompts()).resolves.toEqual({
      prompts: [{ brick: "agent", name: "reason", description: "Think", arguments: [] }],
      failedBricks: ["ui"],
    });
  });

  it("renders through the exact MCP prompt meta-tool and omits blank defaults", async () => {
    mocks.callTool.mockResolvedValue(result({ prompt: "reason", messages: [
      { role: "user", content: "Reason about releases" },
    ] }));
    const prompt: FactoryPrompt = {
      brick: "agent", name: "reason", description: "Think",
      arguments: [{ name: "task", description: "", required: true },
        { name: "mode", description: "", required: false }],
    };
    await expect(renderFactoryPrompt(prompt, { task: "releases", mode: " " })).resolves.toEqual([
      { role: "user", content: "Reason about releases" },
    ]);
    expect(mocks.callTool).toHaveBeenCalledWith({
      name: "render_brick_prompt",
      arguments: { brick_name: "agent", prompt_name: "reason", arguments: '{"task":"releases"}' },
    });
  });
});
