import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const save = vi.hoisted(() => vi.fn());
vi.mock("@/lib/hooks/use-mcp-connection", () => ({ useMcpConnection: () => ({ ready: true, status: "connected" }) }));
vi.mock("../hooks-api", async () => {
  const actual = await vi.importActual<typeof import("../hooks-api")>("../hooks-api");
  return {
    AGENT_LIFECYCLE_EVENTS: actual.AGENT_LIFECYCLE_EVENTS,
    listHooks: async () => [],
    hookAuthoringAvailable: async () => true,
    listInvocableTools: async () => ["agent_read_skill"],
    saveHook: save,
    deleteHook: async () => undefined,
    listRecentFirings: async () => [],
  };
});
import HooksView from "../hooks-view";

// Mirrors lib/api's ApiError: a generic message plus the server's own `reason`.
function apiError(reason: string) {
  return Object.assign(new Error("API 502: Tool 'agent_save_hook' failed"), { reason });
}

describe("HooksView failures", () => {
  it("shows the server's reason instead of the transport message", async () => {
    save.mockRejectedValue(apiError("hook_event_unknown"));
    render(<HooksView />);
    fireEvent.click(await screen.findByRole("button", { name: "New hook" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "h1" } });
    fireEvent.change(screen.getByLabelText("Run this tool"), { target: { value: "agent_read_skill" } });
    fireEvent.click(screen.getByRole("button", { name: "Create hook" }));
    const alert = await screen.findByText(/hook_event_unknown/);
    expect(alert.textContent).toContain("Couldn't create hook.");
    expect(alert.textContent).not.toContain("API 502");
  });
});
