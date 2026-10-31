import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  switchView: vi.fn(),
  health: { connected: true, status: "healthy", totalTools: 763, brickCount: 42, healthyBricks: 42, lastChecked: 1_700_000_000_000 },
  prefs: { theme: "light", density: "compact", language: "de", terminalFontSize: 11, terminalShell: null,
    terminalCompletionEnabled: true, shortcuts: {}, revision: 5 },
}));
vi.mock("@/lib/hooks/use-health", () => ({ useHealth: () => mocks.health }));
vi.mock("@/lib/hooks/use-session-list", () => ({ useSessionList: () => ({ sessions: [{}, {}, {}], loading: false, error: null, refresh: vi.fn() }) }));
vi.mock("@/lib/hooks/use-schedules", () => ({ useSchedules: () => ({ schedules: [{ state: "active" }, { state: "paused" }], loading: false, error: null }) }));
vi.mock("@/lib/workbench-context", () => ({ useOptionalWorkbenchContext: () => ({ switchView: mocks.switchView }) }));
vi.mock("@/components/settings/use-display-preferences", () => ({ useDisplayPreferences: () => ({ preferences: mocks.prefs, loading: false, error: null, refresh: vi.fn() }) }));
vi.mock("@/components/connections/use-external-server-count", () => ({ useExternalServerCount: () => ({ count: 2, mounted: 1 }) }));

import OverviewPanel from "../overview-panel";

beforeEach(() => { mocks.switchView.mockReset(); mocks.health.connected = true; mocks.health.lastChecked = 1_700_000_000_000; });

describe("Settings Overview", () => {
  it("shows a live health hero and truthful stat cards", () => {
    render(<OverviewPanel />);
    expect(screen.getByRole("heading", { name: "Companion X is connected" })).toBeTruthy();
    expect(screen.getByText(/42 of 42 bricks healthy/)).toBeTruthy();
    expect(screen.getByRole("listitem", { name: /Tools available: 763/ })).toBeTruthy();
    expect(screen.getByRole("listitem", { name: /External MCP servers: 2\. 1 mounted/ })).toBeTruthy();
    expect(screen.getByRole("listitem", { name: /Sessions: 3/ })).toBeTruthy();
    expect(screen.getByRole("listitem", { name: /Schedules: 2\. 1 active/ })).toBeTruthy();
  });

  it("drills into the surface that owns each number", () => {
    render(<OverviewPanel />);
    fireEvent.click(screen.getByRole("listitem", { name: /Sessions: 3/ }));
    expect(mocks.switchView).toHaveBeenCalledWith("sessions");
    fireEvent.click(screen.getByRole("listitem", { name: /Tools available/ }));
    expect(mocks.switchView).toHaveBeenCalledWith("capabilities");
    expect(window.location.search).toContain("tab=connections");
  });

  it("reads Display choices from the durable preference instead of hardcoding them", () => {
    render(<OverviewPanel />);
    expect(screen.getByText("light")).toBeTruthy();
    expect(screen.getByText("compact")).toBeTruthy();
    expect(screen.getByText("de")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Open Display →" }));
    expect(mocks.switchView).toHaveBeenCalledWith("settings");
  });

  it("states the disconnected and checking states plainly", () => {
    mocks.health.connected = false;
    const { unmount } = render(<OverviewPanel />);
    expect(screen.getByRole("heading", { name: "Gateway unreachable" })).toBeTruthy();
    unmount();
    mocks.health.lastChecked = null as unknown as number;
    render(<OverviewPanel />);
    expect(screen.getByRole("heading", { name: "Checking the gateway…" })).toBeTruthy();
  });
});
