import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  roster: [] as unknown[],
  refresh: vi.fn(),
  callTool: vi.fn(),
}));
const blue = { id: "blue-crew", name: "Blue Team", description: "", persona_id: "defender", project: "/work/bt", workspace: "", memory_scope: "blue", model: "", triggers: [], revision: 1 };

vi.mock("@/lib/hooks/use-crews", () => ({
  useCrews: () => ({ crews: mocks.roster, defaultId: null, loading: false, error: null, refresh: mocks.refresh }),
}));
vi.mock("@/lib/hooks/use-personas", () => ({ usePersonas: () => ({ personas: [], loading: false, error: null, refresh: vi.fn() }) }));
vi.mock("@/lib/hooks/use-model-catalog", () => ({ useModelCatalog: () => ({ models: [], groups: [], loading: false, error: null, refresh: vi.fn() }) }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import CrewsView from "../crews-view";

const ok = (data: unknown) => ({ tool: "x", result: { schema_version: "v1", ok: true, data } });
const gone = { schema_version: "v1", ok: false, data: null, error: "Crew no longer exists" };

beforeEach(() => {
  mocks.roster = [blue];
  mocks.refresh.mockReset();
  mocks.callTool.mockReset();
  window.history.pushState({}, "", "/crews");
});

describe("Crews delete control", () => {
  it("deletes from the card after confirmation, fenced by revision, then reloads the list", async () => {
    mocks.callTool.mockResolvedValue(ok({ crew_id: "blue-crew", deleted: true }));
    render(<CrewsView />);
    fireEvent.click(screen.getByRole("button", { name: "Delete crew Blue Team" }));
    expect(mocks.callTool).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete crew Blue Team" }));
    await waitFor(() => expect(mocks.refresh).toHaveBeenCalled());
    expect(mocks.callTool).toHaveBeenCalledWith("agent_delete_crew", { crew_id: "blue-crew", expected_revision: 1 });
  });
});

describe("Crews reconcile after a refusal", () => {
  it("reloads the list when starting a session fails because the crew is gone", async () => {
    mocks.callTool.mockResolvedValue(gone);
    render(<CrewsView />);
    fireEvent.click(screen.getByRole("button", { name: "Start session with Blue Team" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Could not start a session with Blue Team");
    expect(mocks.refresh).toHaveBeenCalled();
  });

  it("clears the stale failure banner when the list is refreshed", async () => {
    mocks.callTool.mockResolvedValue(gone);
    render(<CrewsView />);
    fireEvent.click(screen.getByRole("button", { name: "Start session with Blue Team" }));
    await screen.findByText(/Could not start a session/);
    fireEvent.click(screen.getByRole("button", { name: "Refresh crews" }));
    expect(screen.queryByText(/Could not start a session/)).toBeNull();
  });
});
