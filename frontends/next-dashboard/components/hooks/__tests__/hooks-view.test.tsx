import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
const mocks = vi.hoisted(() => ({
  list: vi.fn(), available: vi.fn(), invocable: vi.fn(), save: vi.fn(), remove: vi.fn(), firings: vi.fn(),
}));
vi.mock("@/lib/hooks/use-mcp-connection", () => ({ useMcpConnection: () => ({ ready: true, status: "connected" }) }));
vi.mock("../hooks-api", async () => {
  const actual = await vi.importActual<typeof import("../hooks-api")>("../hooks-api");
  return {
    AGENT_LIFECYCLE_EVENTS: actual.AGENT_LIFECYCLE_EVENTS,
    listHooks: (...args: unknown[]) => mocks.list(...args),
    hookAuthoringAvailable: (...args: unknown[]) => mocks.available(...args),
    listInvocableTools: (...args: unknown[]) => mocks.invocable(...args),
    saveHook: (...args: unknown[]) => mocks.save(...args),
    deleteHook: (...args: unknown[]) => mocks.remove(...args),
    listRecentFirings: (...args: unknown[]) => mocks.firings(...args),
  };
});
import HooksView from "../hooks-view";

const hook = { id: "on-fail-notify", eventType: "workflow.failed", tool: "agent_read_skill", description: "", enabled: true };
beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue([hook]);
  mocks.available.mockReset().mockResolvedValue(true);
  mocks.invocable.mockReset().mockResolvedValue(["agent_read_skill", "workflow_get_run"]);
  mocks.save.mockReset().mockResolvedValue(undefined);
  mocks.remove.mockReset().mockResolvedValue(undefined);
  mocks.firings.mockReset().mockResolvedValue([]);
});

describe("HooksView", () => {
  it("creates a hook by picking a real event and a real tool, not free text", async () => {
    render(<HooksView />);
    fireEvent.click(await screen.findByRole("button", { name: "New hook" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "on-fail-notify" } });
    fireEvent.change(screen.getByLabelText("When"), { target: { value: "workflow.failed" } });
    fireEvent.change(screen.getByLabelText("Run this tool"), { target: { value: "agent_read_skill" } });
    fireEvent.click(screen.getByRole("button", { name: "Create hook" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith({
      id: "on-fail-notify", eventType: "workflow.failed", tool: "agent_read_skill", description: "", enabled: true,
    }));
  });

  it("toggles enabled state on an existing hook", async () => {
    render(<HooksView />);
    fireEvent.click(await screen.findByRole("button", { name: "Enabled" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith({ ...hook, enabled: false }));
  });

  it("deletes a hook", async () => {
    render(<HooksView />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete hook on-fail-notify" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith("on-fail-notify"));
  });

  it("shows no-firings state when history is empty", async () => {
    render(<HooksView />);
    await screen.findByText("No recent firings.");
  });
});
