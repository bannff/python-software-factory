import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  list: vi.fn(), get: vi.fn(), update: vi.fn(),
}));
vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));
vi.mock("@/components/skills/skills-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/skills/skills-api")>()),
  listSkills: (...a: unknown[]) => mocks.list(...a),
  getSkillPolicy: (...a: unknown[]) => mocks.get(...a),
  updateSkillPolicy: (...a: unknown[]) => mocks.update(...a),
}));

import SkillsSettingsPanel from "../skills-settings-panel";

const SKILLS = [
  { id: "cdk-analysis", name: "CDK analysis", description: "Review CDK stacks" },
  { id: "can-analyst", name: "CAN analyst", description: "" },
];

beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue(SKILLS);
  mocks.get.mockReset().mockResolvedValue({ disabledSkills: ["can-analyst"], revision: 3 });
  mocks.update.mockReset().mockImplementation(async (disabled: string[], rev: number) => ({ disabledSkills: disabled, revision: rev + 1 }));
});

describe("Settings → Skills enablement", () => {
  it("renders every installed skill with its owner enablement state", async () => {
    render(<SkillsSettingsPanel />);
    expect(await screen.findByRole("switch", { name: "Enable CDK analysis" })).toHaveProperty("checked", true);
    expect(screen.getByRole("switch", { name: "Enable CAN analyst" })).toHaveProperty("checked", false);
    expect(screen.getByText(/context budget is not offered/i)).toBeTruthy();
  });

  it("writes the full disabled set with the current revision when toggling off", async () => {
    render(<SkillsSettingsPanel />);
    fireEvent.click(await screen.findByRole("switch", { name: "Enable CDK analysis" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(["can-analyst", "cdk-analysis"], 3));
    await waitFor(() => expect(screen.getByRole("switch", { name: "Enable CDK analysis" })).toHaveProperty("checked", false));
  });

  it("re-enables by removing the id and reports a CAS conflict truthfully", async () => {
    render(<SkillsSettingsPanel />);
    fireEvent.click(await screen.findByRole("switch", { name: "Enable CAN analyst" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith([], 3));
    mocks.update.mockRejectedValueOnce(new Error("agent_skill_policy_conflict"));
    fireEvent.click(screen.getByRole("switch", { name: "Enable CDK analysis" }));
    expect((await screen.findByRole("alert")).textContent).toContain("changed elsewhere");
  });
});
