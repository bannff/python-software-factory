import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  roster: {
    crews: [
      { id: "redteam-crew", name: "Red Team", description: "Offensive sweep", persona_id: "redteam", project: "/work/rt", workspace: "", memory_scope: "redteam", model: "openrouter/x/y", triggers: ["scan"], revision: 3 },
      { id: "blue-crew", name: "Blue Team", description: "", persona_id: "defender", project: "/work/bt", workspace: "", memory_scope: "blue", model: "", triggers: [], revision: 1 },
    ],
    defaultId: "redteam-crew" as string | null,
    loading: false,
    error: null as string | null,
    refresh: vi.fn(),
  },
  callTool: vi.fn(),
}));

vi.mock("@/lib/hooks/use-crews", () => ({ useCrews: () => mocks.roster }));
vi.mock("@/lib/hooks/use-personas", () => ({
  usePersonas: () => ({ personas: [{ id: "redteam", name: "Red Team" }, { id: "defender", name: "Defender" }], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/hooks/use-model-catalog", () => ({
  useModelCatalog: () => ({ models: [], groups: [{ provider: "openrouter", models: [{ model_id: "openrouter/x/y", provider: "openrouter", model: "x/y" }] }], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import CrewsView from "../crews-view";

beforeEach(() => {
  mocks.callTool.mockReset().mockResolvedValue({});
  mocks.roster.refresh.mockReset();
  mocks.roster.error = null;
  mocks.roster.crews = [
    { id: "redteam-crew", name: "Red Team", description: "Offensive sweep", persona_id: "redteam", project: "/work/rt", workspace: "", memory_scope: "redteam", model: "openrouter/x/y", triggers: ["scan"], revision: 3 },
    { id: "blue-crew", name: "Blue Team", description: "", persona_id: "defender", project: "/work/bt", workspace: "", memory_scope: "blue", model: "", triggers: [], revision: 1 },
  ];
  mocks.roster.defaultId = "redteam-crew";
  window.history.pushState({}, "", "/crews");
});

describe("CrewsView card gallery", () => {
  it("shows discoverable cards with the Default badge and summaries", () => {
    render(<CrewsView />);
    expect(screen.getByRole("heading", { name: "Crews" })).toBeTruthy();
    expect(screen.getByText("Red Team")).toBeTruthy();
    expect(screen.getByText("Blue Team")).toBeTruthy();
    expect(screen.getByText("Default")).toBeTruthy();
    // Summaries: persona + project + inherit fallback for the empty model.
    expect(screen.getAllByText("redteam").length).toBeGreaterThan(0);
    expect(screen.getByText("/work/bt")).toBeTruthy();
    expect(screen.getByText("Inherit")).toBeTruthy();
    expect(screen.getByText("Red Team").getAttribute("title")).toBe("Red Team");
    expect(screen.getAllByText("Persona")[0].tagName).toBe("DT");
    expect(screen.getByText("/work/bt").tagName).toBe("DD");
    expect(screen.getAllByText("Persona")[0].getAttribute("title"))
      .toBe("Which assistant personality this crew uses");
    expect(screen.getAllByText("Model")[0].getAttribute("title"))
      .toBe("Which AI engine this crew uses");
    expect(screen.getByText("/work/bt").getAttribute("title")).toBe("/work/bt");
    // Dashed New-crew affordance.
    expect(screen.getByRole("button", { name: "New crew" })).toBeTruthy();
  });

  it("explains the empty state on the New-crew card", () => {
    mocks.roster.crews = [];
    mocks.roster.defaultId = null;
    render(<CrewsView />);
    expect(screen.getByText(/No crews yet/i)).toBeTruthy();
  });

  it("renders retry on a degraded roster", () => {
    mocks.roster.error = "Crews unavailable";
    render(<CrewsView />);
    expect(screen.getByRole("alert").textContent).toContain("Crews unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mocks.roster.refresh).toHaveBeenCalled();
  });

  it("creates a crew through the real MCP tool", async () => {
    render(<CrewsView />);
    fireEvent.click(screen.getByRole("button", { name: "New crew" }));
    fireEvent.change(screen.getByLabelText("Crew ID"), { target: { value: "green-crew" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Green" } });
    fireEvent.change(screen.getByLabelText("Persona"), { target: { value: "defender" } });
    fireEvent.change(screen.getByLabelText("Project path"), { target: { value: "/work/gt" } });
    fireEvent.change(screen.getByLabelText("Memory scope"), { target: { value: "green" } });
    fireEvent.click(screen.getByRole("button", { name: "Create crew" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("agent_create_crew", expect.objectContaining({
      crew_id: "green-crew", name: "Green", persona_id: "defender", project: "/work/gt", memory_scope: "green",
    })));
  });

  it("sets a non-default crew as the default with revision fencing", async () => {
    render(<CrewsView />);
    fireEvent.click(screen.getByRole("button", { name: "Edit crew Blue Team" }));
    fireEvent.click(screen.getByRole("button", { name: /Set as default/ }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("agent_set_default_crew", {
      crew_id: "blue-crew", expected_revision: 1,
    }));
  });
});
