import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  list: vi.fn(), read: vi.fn(), add: vi.fn(), remove: vi.fn(),
  // Kept so the pre-change panel (which imported `skillAuthoringAvailable`)
  // can still be driven when this suite runs against the base revision.
  legacyAvailable: vi.fn(),
  caps: vi.fn(),
}));
vi.mock("@/lib/hooks/use-mcp-connection", () => ({
  useMcpConnection: () => ({ ready: true, status: "connected" }),
}));
vi.mock("../skills-api", () => ({
  listSkills: (...args: unknown[]) => mocks.list(...args),
  readSkill: (...args: unknown[]) => mocks.read(...args),
  addSkill: (...args: unknown[]) => mocks.add(...args),
  deleteSkill: (...args: unknown[]) => mocks.remove(...args),
  skillAuthoringAvailable: (...args: unknown[]) => mocks.legacyAvailable(...args),
}));
vi.mock("@/lib/authoring-capabilities", async (importOriginal) => ({
  ...(await importOriginal<typeof AuthoringCapabilitiesModule>()),
  getAuthoringCapabilities: (...args: unknown[]) => mocks.caps(...args),
}));

import type * as AuthoringCapabilitiesModule from "@/lib/authoring-capabilities";
import SkillsView from "../skills-view";

const LIFECYCLE = { add: false, create: false, update: false, delete: false, fork: false, reset: false };
function capabilities(skills: Partial<typeof LIFECYCLE>) {
  return {
    config: { read: true, write: true },
    skills: { ...LIFECYCLE, ...skills },
    steering: { ...LIFECYCLE }, agent_templates: { ...LIFECYCLE },
    roots: {
      config: { path: "/data/agent-config", source: "env" as const },
      skills: { path: "/data/agent-skills", source: "env" as const },
      steering: { path: "/data/agent-steering", source: "default" as const },
    },
  };
}

beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue([{ id: "review", name: "Review", description: "Check evidence" }]);
  mocks.read.mockReset().mockResolvedValue({ id: "review", name: "Review", description: "Check evidence", body: "Read the diff." });
  mocks.add.mockReset().mockResolvedValue({ id: "new-skill", name: "New Skill", description: "Added" });
  mocks.remove.mockReset().mockResolvedValue(undefined);
  mocks.legacyAvailable.mockReset().mockResolvedValue(true);
  mocks.caps.mockReset().mockResolvedValue(capabilities({ add: true, delete: true }));
});

describe("SkillsView", () => {
  it("lists, filters, and reads skill instructions", async () => {
    render(<SkillsView />);
    fireEvent.click(await screen.findByRole("button", { name: /Review/ }));
    expect(await screen.findByText("Read the diff.")).toBeTruthy();
    expect(mocks.read).toHaveBeenCalledWith("review");
    fireEvent.change(screen.getByLabelText("Search skills"), { target: { value: "missing" } });
    expect(screen.getByText("No matching skills.")).toBeTruthy();
  });

  it("adds a skill when skills.add is allowed", async () => {
    mocks.read.mockImplementation(async (id: string) => ({
      id, name: id === "new-skill" ? "New Skill" : "Review", description: "Added", body: "Use evidence.",
    }));
    render(<SkillsView />);
    fireEvent.click(await screen.findByRole("button", { name: "Add skill" }));
    fireEvent.change(screen.getByLabelText("ID"), { target: { value: "new-skill" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "New Skill" } });
    fireEvent.change(screen.getByLabelText("Instructions"), { target: { value: "Use evidence." } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add skill" })[1]);
    await waitFor(() => expect(mocks.add).toHaveBeenCalledWith({
      skillId: "new-skill", name: "New Skill", description: "", body: "Use evidence.",
    }));
    expect(await screen.findByText("Use evidence.")).toBeTruthy();
  });

  it("keeps reads available and names the variable when skills.add is denied", async () => {
    mocks.caps.mockResolvedValue(capabilities({ delete: true }));
    render(<SkillsView />);
    expect(await screen.findByText(/FACTORY_AGENT_AUTHORING_SKILLS=add/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add skill" })).toBeNull();
    expect(screen.getByRole("button", { name: /Review/ })).toBeTruthy();
  });

  it("shows Delete and NOT Add when only skills.delete is allowed", async () => {
    mocks.caps.mockResolvedValue(capabilities({ delete: true }));
    render(<SkillsView />);
    fireEvent.click(await screen.findByRole("button", { name: /Review/ }));
    await screen.findByText("Read the diff.");
    expect(screen.queryByRole("button", { name: "Add skill" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete skill" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete skill" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith("review"));
  });

  it("shows Add and NOT Delete when only skills.add is allowed", async () => {
    mocks.caps.mockResolvedValue(capabilities({ add: true }));
    render(<SkillsView />);
    fireEvent.click(await screen.findByRole("button", { name: /Review/ }));
    await screen.findByText("Read the diff.");
    expect(screen.getByRole("button", { name: "Add skill" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Delete skill" })).toBeNull();
    expect(await screen.findByText(/FACTORY_AGENT_AUTHORING_SKILLS=delete/)).toBeTruthy();
  });

  it("surfaces an authoring root failure verbatim on write", async () => {
    mocks.add.mockRejectedValue(new Error("authoring_root_unavailable"));
    render(<SkillsView />);
    fireEvent.click(await screen.findByRole("button", { name: "Add skill" }));
    fireEvent.change(screen.getByLabelText("ID"), { target: { value: "new-skill" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "New Skill" } });
    fireEvent.change(screen.getByLabelText("Instructions"), { target: { value: "Use evidence." } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add skill" })[1]);
    expect((await screen.findByRole("alert")).textContent).toContain("authoring_root_unavailable");
  });
});
