import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn(), catalog: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.callTool }));
vi.mock("@/lib/tool-catalog", () => ({ fetchToolCatalog: mocks.catalog }));

import { getTemplateIdPattern, listUserTemplates } from "../agent-template-api";

beforeEach(() => { mocks.callTool.mockReset(); mocks.catalog.mockReset(); });

describe("listUserTemplates", () => {
  it("reads ids and fork provenance from the items agent_list_config_items returns", async () => {
    mocks.callTool.mockResolvedValue({ schema_version: "v1", ok: true, data: { success: true, result: { ok: true, items: [
      { kind: "agent", id: "lc-template", path: "/s/agents/lc-template.yaml" },
      { kind: "agent", id: "other", path: "/s/agents/other.yaml", forked_from: "builtin" },
    ] } } });

    expect(await listUserTemplates()).toEqual([
      { id: "lc-template", forkedFrom: null },
      { id: "other", forkedFrom: "builtin" },
    ]);
  });
});

describe("getTemplateIdPattern", () => {
  it("reads the agent ID rule from the fork tool's published schema", async () => {
    mocks.catalog.mockResolvedValue({ tools: [
      { qualified_name: "agent_fork_agent", input_schema: { properties: {
        new_agent_id: { type: "string", pattern: "^[a-z0-9][a-z0-9_-]{0,127}$" } } } },
    ] });
    await expect(getTemplateIdPattern()).resolves.toBe("^[a-z0-9][a-z0-9_-]{0,127}$");
    mocks.catalog.mockResolvedValue({ tools: [] });
    await expect(getTemplateIdPattern()).resolves.toBeNull();
  });
});
