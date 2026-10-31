import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  requested: null as string | null,
  health: {
    connected: true, status: "healthy", totalTools: 42, brickCount: 20,
    healthyBricks: 19, bricks: {}, timeline: null, lastChecked: 123,
  },
  catalog: {
    models: [], loading: false, error: null as string | null, refresh: vi.fn(),
    groups: [
      { provider: "openrouter", models: [{ model_id: "a", provider: "openrouter", model: "a" }] },
      { provider: "bedrock", models: [
        { model_id: "b", provider: "bedrock", model: "b" },
        { model_id: "c", provider: "bedrock", model: "c" },
      ] },
    ],
  },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(mocks.requested ? `section=${mocks.requested}` : ""),
}));
vi.mock("@/lib/hooks/use-health", () => ({ useHealth: () => mocks.health }));
vi.mock("@/lib/hooks/use-schedules", () => ({ useSchedules: () => ({ schedules: [], loading: false, error: null }) }));
vi.mock("@/lib/hooks/use-session-list", () => ({ useSessionList: () => ({ sessions: [], loading: false, error: null, refresh: vi.fn() }) }));
vi.mock("@/components/connections/use-external-server-count", () => ({ useExternalServerCount: () => ({ count: 0, mounted: 0 }) }));
vi.mock("@/lib/hooks/use-mcp-connection", () => ({
  useMcpConnection: () => ({ ready: true, status: "connected" }),
}));
vi.mock("@/lib/hooks/use-model-catalog", () => ({ useModelCatalog: () => mocks.catalog }));
vi.mock("@/components/settings/use-chat-preferences", () => ({
  useChatPreferences: () => ({ preferences: { plainDiffs: false, hiddenModels: [], revision: 0 }, loading: false, error: null, refresh: vi.fn() }),
  announceChatPreferences: vi.fn(),
}));
vi.mock("@/components/settings/use-display-preferences", () => ({
  useDisplayPreferences: () => ({ preferences: { theme: "dark", terminalFontSize: 14, density: "comfortable", language: "en", shortcuts: {}, revision: 1 }, loading: false, error: null, refresh: vi.fn() }),
  announceDisplayPreferences: vi.fn(),
}));
vi.mock("next-themes", () => ({ useTheme: () => ({ setTheme: vi.fn() }) }));
vi.mock("@/lib/api", () => ({
  callTool: vi.fn().mockResolvedValue({ tool: "get_metrics_summary", result: { schema_version: "v1", ok: true, data: {
    started_at: 1234567890, llm: { interactions: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, cost_usd: 0, last_latency_ms: null },
    agent: { executions: 0 }, tools: { invocations: 0 }, logs: { total: 0, by_severity: {} }, errors: 0,
  } } }),
}));

import SettingsView from "../settings-view";

beforeEach(() => {
  mocks.requested = null;
  window.history.pushState({}, "", "/settings");
  mocks.catalog.error = null;
});

describe("SettingsView", () => {
  it("renders the complete Settings section inventory", () => {
    render(<SettingsView />);
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Overview", "Import & Export", "Chat", "Display", "Voice", "Notifications",
      "Shortcuts", "Skills", "Channels", "Browser", "Computer Use", "Remote Crew",
      "Privacy", "Security", "Secrets", "Usage", "Developer", "About", "Releases",
    ]);
  });

  it("opens a valid bookmarkable Settings section", () => {
    mocks.requested = "imports";
    render(<SettingsView />);
    expect(screen.getByRole("tab", { name: "Import & Export" }).getAttribute("aria-selected"))
      .toBe("true");
    expect(screen.getByRole("button", { name: "Preview import" })).toBeTruthy();
  });

  it("uses a roving tabindex and arrow-key navigation", () => {
    render(<SettingsView />);
    const [overview, imports] = screen.getAllByRole("tab");
    expect(overview.getAttribute("tabindex")).toBe("0");
    expect(imports.getAttribute("tabindex")).toBe("-1");

    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Import & Export" }).getAttribute("aria-selected")).toBe("true");
    expect(imports.getAttribute("tabindex")).toBe("0");

    fireEvent.keyDown(screen.getByRole("tablist"), { key: "End" });
    expect(screen.getByRole("tab", { name: "Releases" }).getAttribute("aria-selected")).toBe("true");
  });

  it("shows truthful Overview config summaries from live health", () => {
    render(<SettingsView />);
    expect(screen.getByRole("heading", { name: "Companion X is connected" })).toBeTruthy();
    expect(screen.getByText(/19 of 20 bricks healthy/)).toBeTruthy();
    expect(screen.getByRole("listitem", { name: /Tools available: 42/ })).toBeTruthy();
  });

  it("mounts the merge-only Migration preview without faking progress", () => {
    render(<SettingsView />);
    fireEvent.click(screen.getByRole("tab", { name: "Import & Export" }));
    expect(screen.getByText(/Adds missing items only/i)).toBeTruthy();
    expect(screen.getByText(/never overwrites or deletes/i)).toBeTruthy();
    expect(screen.getByText(/Schedules arrive paused/i)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Preview import" }) as HTMLButtonElement).disabled)
      .toBe(false);
    expect(screen.queryByText(/eligible items/i)).toBeNull();
  });

  it("mounts real diff and model visibility preferences", () => {
    render(<SettingsView />);
    fireEvent.click(screen.getByRole("tab", { name: "Chat" }));
    expect(screen.getByRole("checkbox", { name: "Plain diffs" })).toBeTruthy();
    expect(screen.getByText("Model picker visibility")).toBeTruthy();
    expect(screen.getByText("a")).toBeTruthy();
    expect(screen.getByText("b")).toBeTruthy();
    expect(screen.getByText("c")).toBeTruthy();
  });

  it("mounts real theme and Terminal font controls", () => {
    render(<SettingsView />);
    fireEvent.click(screen.getByRole("tab", { name: "Display" }));
    expect((screen.getByRole("combobox", { name: "Theme" }) as HTMLSelectElement).value).toBe("dark");
    expect((screen.getByRole("slider", { name: "Terminal font size" }) as HTMLInputElement).value).toBe("14");
  });

  it("mounts the real Secrets panel with no reveal affordance", async () => {
    render(<SettingsView />);
    fireEvent.click(screen.getByRole("tab", { name: "Secrets" }));
    expect(await screen.findByText(/No secrets stored yet|Loading secrets/)).toBeTruthy();
    expect(screen.queryByLabelText(/reveal/i)).toBeNull();
  });

});
