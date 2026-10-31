import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.callTool }));

import { authoringGateNotice, getAuthoringCapabilities, resetAuthoringCapabilities,
  type AuthoringCapabilities } from "../authoring-capabilities";

const DTO = {
  config: { read: true, write: false },
  skills: { add: false, create: false, update: false, delete: true, fork: false, reset: false },
  steering: { add: false, create: false, update: true, delete: false, fork: false, reset: false },
  agent_templates: { add: false, create: true, update: false, delete: false, fork: true, reset: false },
  roots: {
    config: { path: "/data/agent-config", source: "env" },
    skills: { path: "/data/agent-skills", source: "env" },
    steering: { path: ".storage/agent-steering", source: "default" },
  },
};

function envelope(data: unknown) {
  return { tool: "agent_authoring_capabilities", result: { ok: true, data } };
}

beforeEach(() => {
  mocks.callTool.mockReset();
  resetAuthoringCapabilities();
});

describe("authoring capabilities loader", () => {
  it("returns the per-action DTO and normalizes every surface", async () => {
    mocks.callTool.mockResolvedValue(envelope(DTO));
    const caps = await getAuthoringCapabilities();
    expect(mocks.callTool).toHaveBeenCalledWith("agent_authoring_capabilities");
    expect(caps.config).toEqual({ read: true, write: false });
    expect(caps.skills).toMatchObject({ add: false, delete: true });
    expect(caps.agent_templates).toMatchObject({ create: true, fork: true, reset: false });
    expect(caps.roots.skills).toEqual({ path: "/data/agent-skills", source: "env" });
    expect(caps.roots.steering.source).toBe("default");
  });

  it("memoizes the probe until reset", async () => {
    mocks.callTool.mockResolvedValue(envelope(DTO));
    const [first, second] = await Promise.all([getAuthoringCapabilities(), getAuthoringCapabilities()]);
    expect(first).toBe(second);
    await getAuthoringCapabilities();
    expect(mocks.callTool).toHaveBeenCalledTimes(1);
    resetAuthoringCapabilities();
    await getAuthoringCapabilities();
    expect(mocks.callTool).toHaveBeenCalledTimes(2);
  });

  it("clears the memo when the probe fails so a retry can succeed", async () => {
    mocks.callTool.mockRejectedValueOnce(new Error("mcp down"));
    await expect(getAuthoringCapabilities()).rejects.toThrow("mcp down");
    mocks.callTool.mockResolvedValue(envelope(DTO));
    await expect(getAuthoringCapabilities()).resolves.toMatchObject({ config: { read: true } });
  });

  it("defaults every action to false when a surface is missing", async () => {
    mocks.callTool.mockResolvedValue(envelope({ config: { read: true } }));
    const caps = await getAuthoringCapabilities();
    expect(caps.skills).toEqual({ add: false, create: false, update: false, delete: false, fork: false, reset: false });
    expect(caps.roots.config).toEqual({ path: "", source: "default" });
  });
});

describe("authoringGateNotice", () => {
  it("names the surface variable and the exact write root", () => {
    const caps = { ...DTO } as unknown as AuthoringCapabilities;
    expect(authoringGateNotice(caps, "skills", "add"))
      .toContain("FACTORY_AGENT_AUTHORING_SKILLS=add");
    expect(authoringGateNotice(caps, "skills", "add")).toContain("/data/agent-skills");
    expect(authoringGateNotice(caps, "agent_templates", "delete"))
      .toContain("FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES=delete");
    expect(authoringGateNotice(caps, "agent_templates", "delete")).toContain("/data/agent-config");
  });
});
