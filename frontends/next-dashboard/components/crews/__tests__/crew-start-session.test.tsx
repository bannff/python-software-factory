import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  crews: [
    { id: "redteam-crew", name: "Red Team", description: "", persona_id: "redteam", project: "/work/rt", workspace: "", memory_scope: "redteam", model: "", triggers: [], revision: 3 },
    { id: "blue-crew", name: "Blue Team", description: "", persona_id: "defender", project: "/work/bt", workspace: "", memory_scope: "blue", model: "", triggers: [], revision: 1 },
  ],
  callTool: vi.fn(),
}));

vi.mock("@/lib/hooks/use-crews", () => ({
  useCrews: () => ({ crews: mocks.crews, defaultId: "redteam-crew", loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/hooks/use-personas", () => ({ usePersonas: () => ({ personas: [], loading: false, error: null, refresh: vi.fn() }) }));
vi.mock("@/lib/hooks/use-model-catalog", () => ({ useModelCatalog: () => ({ models: [], groups: [], loading: false, error: null, refresh: vi.fn() }) }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args), listTools: async () => ({ tools: [], count: 0 }) }));

import CrewsView from "../crews-view";

const ok = (data: unknown) => ({ schema_version: "v1", ok: true, data });

beforeEach(() => {
  mocks.callTool.mockReset().mockImplementation(async (tool: string, args: Record<string, unknown>) => {
    if (tool === "agent_resolve_crew") {
      return ok({ crew_id: args.crew_id, persona_id: "defender", model_id: "m", project: "/work/bt", workspace: "", memory_scope: "blue" });
    }
    return ok({ session: {
      session_id: "s-new", thread_id: "t-new", title: "New session", agent_id: "defender", model: "m",
      updated_at: "2026-09-13T00:00:00Z", archived_at: null, revision: 1, crew_id: args.crew_id, memory_scope: "blue",
    } });
  });
  window.history.pushState({}, "", "/crews");
});

describe("Crew card Start session", () => {
  it("starts a session from a non-default crew through the single create path", async () => {
    render(<CrewsView />);
    fireEvent.click(screen.getByRole("button", { name: "Start session with Blue Team" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_create", expect.objectContaining({
      crew_id: "blue-crew", agent_id: "defender",
    })));
    expect(mocks.callTool).toHaveBeenCalledWith("agent_resolve_crew", { crew_id: "blue-crew" });
    expect((await screen.findByRole("status")).textContent).toContain("Blue Team");
  });

  it("reports a failed start instead of staying silent", async () => {
    mocks.callTool.mockResolvedValue({ schema_version: "v1", ok: false, error: "nope" });
    render(<CrewsView />);
    fireEvent.click(screen.getByRole("button", { name: "Start session with Blue Team" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Blue Team");
  });
});
