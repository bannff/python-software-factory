import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
const mocks = vi.hoisted(() => ({
  requested: null as string | null,
  health: { connected: true, status: "healthy", totalTools: 42, brickCount: 20,
    healthyBricks: 19, bricks: {}, timeline: null, lastChecked: 123 },
  catalog: { models: [], loading: false, error: null, refresh: vi.fn(), groups: [] },
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
vi.mock("@/components/settings/approval-policy-api", () => ({
  getApprovalPolicy: vi.fn().mockResolvedValue({ toolNames: [], revision: 0 }),
  listApprovalToolNames: vi.fn().mockResolvedValue(["devtools_run_command"]),
  updateApprovalPolicy: vi.fn(),
}));
vi.mock("@/lib/api", () => ({
  callTool: vi.fn().mockResolvedValue({ tool: "get_metrics_summary", result: { schema_version: "v1", ok: true, data: {
    started_at: 1234567890, llm: { interactions: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, cost_usd: 0, last_latency_ms: null },
    agent: { executions: 0 }, tools: { invocations: 0 }, logs: { total: 0, by_severity: {} }, errors: 0,
  } } }),
}));
import SettingsView from "../settings-view";

beforeEach(() => { mocks.requested = null; window.history.pushState({}, "", "/settings"); });
const open = (name: string) => {
  render(<SettingsView />);
  fireEvent.click(screen.getByRole("tab", { name }));
};

describe("Settings disclosure panels", () => {
  it("mounts the remappable keyboard shortcut reference", () => {
    open("Shortcuts");
    expect(screen.getByText("Open or close command palette")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Change shortcut for Open or close command palette" })).toBeTruthy();
    expect(screen.getByText("K")).toBeTruthy();
    expect(screen.queryByText(/overrides are not available yet/i)).toBeNull();
  });
  it("offers owner skill enablement and hands browse/create to Agent Capabilities", () => {
    open("Skills");
    expect(screen.getByRole("link", { name: /Browse or create/ }).getAttribute("href"))
      .toBe("/capabilities?tab=skills");
    expect(screen.getByText(/context budget is not offered/i)).toBeTruthy();
  });
  it("routes Channels to delivery and connection owners", () => {
    open("Channels");
    expect(screen.getByRole("link", { name: /Open Notifications/ }).getAttribute("href"))
      .toBe("/settings?section=notifications");
    expect(screen.getByRole("link", { name: /Open Connections/ }).getAttribute("href"))
      .toBe("/capabilities?tab=connections");
  });
  it("shows the Browser engine section and states what does not apply", () => {
    open("Browser");
    expect(screen.getByText("Interactive page control")).toBeTruthy();
    expect(screen.getByText(/installing Playwright .* attaching a hosted-engine token/i)).toBeTruthy();
  });
  it("frames Computer Use as a mounted desktop server scoped by the approval list", () => {
    open("Computer Use");
    expect(screen.getByText("Scope = your approval list")).toBeTruthy();
    expect(screen.getByText("Protected fields")).toBeTruthy();
    expect(screen.getByText(/Not applicable here: a separate allowed\/denied-app list/)).toBeTruthy();
  });
  it("keeps Remote Crew local-only", () => {
    open("Remote Crew");
    expect(screen.getByText("This device")).toBeTruthy();
    expect(screen.getByText("Remote instances")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /connect|provision/i })).toBeNull();
  });
  it("discloses telemetry without a fake opt-out", () => {
    open("Privacy");
    expect(screen.getByText("What may be recorded")).toBeTruthy();
    expect(screen.getByText(/cannot turn this collection off for only your account/i)).toBeTruthy();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
  it("discloses current Security limits", async () => {
    open("Security");
    expect(screen.getByText("Local commands")).toBeTruthy();
    expect(screen.getByText(/Only tools you add below ask you/i)).toBeTruthy();
    expect(await screen.findByText(/No tools require approval. Agents run unattended/i)).toBeTruthy();
  });
  it("discloses Developer status without fake switches", () => {
    open("Developer");
    expect(screen.getByText("Developer tools")).toBeTruthy();
    expect(screen.getByText("Feature previews")).toBeTruthy();
    expect(screen.getByText(/cannot be switched from this page/i)).toBeTruthy();
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
  it("shows About package version, live health, and a real diagnostics download", () => {
    open("About");
    expect(screen.getByText("Dashboard version")).toBeTruthy();
    expect(screen.getByText("0.1.0")).toBeTruthy();
    expect(screen.getByText("API status")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Download diagnostics bundle/ })).toBeTruthy();
    expect(screen.getByText("Build")).toBeTruthy();
    expect(screen.getByText(/report-problem workflow is not available/i)).toBeTruthy();
  });
  it("shows browser read-aloud and disabled dictation status", () => {
    open("Voice");
    expect(screen.getByText("Read aloud")).toBeTruthy();
    expect(screen.getByText("Dictation")).toBeTruthy();
    expect(screen.getByText(/Microphone access is disabled/i)).toBeTruthy();
    expect(screen.getByText(/preferred voice or dictation engine is not available/i)).toBeTruthy();
  });
});
