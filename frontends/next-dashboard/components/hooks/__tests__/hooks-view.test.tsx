import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
const mocks = vi.hoisted(() => ({
  list: vi.fn(), available: vi.fn(), invocable: vi.fn(), save: vi.fn(), setEnabled: vi.fn(), remove: vi.fn(), firings: vi.fn(),
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
    setHookEnabled: (...args: unknown[]) => mocks.setEnabled(...args),
    deleteHook: (...args: unknown[]) => mocks.remove(...args),
    listRecentFirings: (...args: unknown[]) => mocks.firings(...args),
  };
});
import HooksView from "../hooks-view";

const hook = { id: "on-fail-notify", eventType: "workflow.failed", tool: "agent_read_skill", description: "", enabled: true, origin: "authored" as const };
beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue([hook]);
  mocks.available.mockReset().mockResolvedValue(true);
  mocks.invocable.mockReset().mockResolvedValue(["agent_read_skill", "workflow_get_run"]);
  mocks.save.mockReset().mockResolvedValue(undefined);
  mocks.setEnabled.mockReset().mockResolvedValue(undefined);
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
      id: "on-fail-notify", eventType: "workflow.failed", tool: "agent_read_skill", description: "", enabled: true, origin: "authored",
    }));
  });

  it("refuses a tool name that is not in the live tool catalog", async () => {
    render(<HooksView />);
    fireEvent.click(await screen.findByRole("button", { name: "New hook" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "x" } });
    fireEvent.change(screen.getByLabelText("Run this tool"), { target: { value: "agent_read_" } });
    expect(screen.getByText("Unknown tool: pick one from the list.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Create hook" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Run this tool"), { target: { value: "agent_read_skill" } });
    expect(screen.queryByText(/Unknown tool/)).toBeNull();
    expect((screen.getByRole("button", { name: "Create hook" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows platform rows with readable labels and keeps raw codes in the tooltip", async () => {
    mocks.list.mockResolvedValue([{ ...hook, id: "auto-improve", origin: "system",
      eventType: "reward.computed", tool: "mcp:improvement_dispatch" }]);
    render(<HooksView />);
    const when = await screen.findByText("When Reward computed");
    expect(when.getAttribute("title")).toBe("reward.computed");
    const runs = screen.getByText("Runs: improvement_dispatch");
    expect(runs.getAttribute("title")).toBe("mcp:improvement_dispatch");
  });

  it("toggles enabled state on an existing hook", async () => {
    render(<HooksView />);
    fireEvent.click(await screen.findByRole("button", { name: "Enabled" }));
    await waitFor(() => expect(mocks.setEnabled).toHaveBeenCalledWith("on-fail-notify", false));
    expect(mocks.save).not.toHaveBeenCalled();
  });

  it("lists platform subscriptions as read-only: no toggle, no delete", async () => {
    mocks.list.mockResolvedValue([{ ...hook, id: "graph-projection", origin: "system" }]);
    render(<HooksView />);
    await screen.findByText("graph-projection");
    expect(screen.getByText("System")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Enabled" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete hook graph-projection" })).toBeNull();
  });

  it("deletes a hook", async () => {
    render(<HooksView />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete hook on-fail-notify" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete hook on-fail-notify" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith("on-fail-notify"));
  });

  it("shows an empty event-history state", async () => {
    render(<HooksView />);
    await screen.findByText("No recent events of this type.");
  });
});
