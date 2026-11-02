import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ callTool }));

import { listUserTemplateIds } from "../agent-template-api";

beforeEach(() => callTool.mockReset());

describe("listUserTemplateIds", () => {
  it("reads ids from the {kind, id, path} items agent_list_config_items returns", async () => {
    callTool.mockResolvedValue({ schema_version: "v1", ok: true, data: { success: true, result: { ok: true, items: [
      { kind: "agent", id: "lc-template", path: "/s/agents/lc-template.yaml" },
      { kind: "agent", id: "other", path: "/s/agents/other.yaml" },
    ] } } });

    expect(await listUserTemplateIds()).toEqual(["lc-template", "other"]);
  });
});
