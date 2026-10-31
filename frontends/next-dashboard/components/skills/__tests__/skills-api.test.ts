import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.callTool }));

import { addSkill, deleteSkill, listSkills, readSkill } from "../skills-api";

beforeEach(() => { mocks.callTool.mockReset(); });

describe("Skills MCP API", () => {
  it("lists and reads typed skills", async () => {
    mocks.callTool.mockResolvedValueOnce({ tool: "agent_list_skills", result: {
      ok: true, data: { skills: [{ id: "review", name: "Review", description: "Check" }] },
    }}).mockResolvedValueOnce({ tool: "agent_read_skill", result: {
      ok: true, data: { id: "review", name: "Review", description: "Check", body: "Read evidence." },
    }});
    await expect(listSkills()).resolves.toEqual([{ id: "review", name: "Review", description: "Check" }]);
    await expect(readSkill("review")).resolves.toEqual({
      id: "review", name: "Review", description: "Check", body: "Read evidence.",
    });
    expect(mocks.callTool).toHaveBeenLastCalledWith("agent_read_skill", { skill_id: "review" });
  });

  it("sends exact add arguments", async () => {
    mocks.callTool.mockResolvedValue({ tool: "agent_add_skill", result: { ok: true, data: {
      created: true, skill: { id: "new-skill", name: "New", description: "Added" },
    } } });
    await addSkill({ skillId: "new-skill", name: "New", description: "Added", body: "Do work." });
    expect(mocks.callTool).toHaveBeenCalledWith("agent_add_skill", {
      skill_id: "new-skill", name: "New", description: "Added", body: "Do work.",
    });
  });

  it("rejects failed ToolResult envelopes", async () => {
    mocks.callTool.mockResolvedValue({ tool: "agent_read_skill", result: {
      ok: false, error: "skill_not_found",
    } });
    await expect(readSkill("missing")).rejects.toThrow("skill_not_found");
  });

  it("sends exact delete arguments and resolves on success", async () => {
    mocks.callTool.mockResolvedValue({ tool: "agent_delete_skill", result: { ok: true, data: {
      deleted: true, skill_id: "new-skill",
    } } });
    await expect(deleteSkill("new-skill")).resolves.toBeUndefined();
    expect(mocks.callTool).toHaveBeenCalledWith("agent_delete_skill", { skill_id: "new-skill" });
  });

  it("rejects a delete that did not actually remove the skill", async () => {
    mocks.callTool.mockResolvedValue({ tool: "agent_delete_skill", result: {
      ok: false, error: "skill_not_found",
    } });
    await expect(deleteSkill("missing")).rejects.toThrow("skill_not_found");
  });
});
