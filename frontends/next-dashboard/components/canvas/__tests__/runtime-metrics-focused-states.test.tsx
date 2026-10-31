import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  focused: { entries: [], loading: false, error: null as string | null, available: true },
}));
vi.mock("@/lib/hooks/use-focused-run-entries", () => ({
  useFocusedRunEntries: () => mocks.focused,
}));
vi.mock("@/lib/hooks/use-live-tool-stream", () => ({
  useLiveToolStream: () => ({ entries: [{ id: "broad", type: "tool_call", title: "other", status: "completed", timestamp: 1, workflow_run_id: "other-run" }], connected: true }),
}));
vi.mock("@/lib/hooks/use-health", () => ({ useHealth: () => ({ timeline: { history: { available: true } } }) }));
vi.mock("@/lib/hooks/use-timeline-focus", () => ({ setTimelineFocus: vi.fn() }));
vi.mock("@/lib/workbench-context", () => ({
  useWorkbenchContext: () => ({ focusedRunId: "run-a", clearRunFocus: vi.fn(), navigationRef: null }),
}));
vi.mock("../metrics-navigation-actions", () => ({ MetricsNavigationActions: () => null }));

import RuntimeMetricsView from "../runtime-metrics-view";

beforeEach(() => {
  mocks.focused = { entries: [], loading: false, error: null, available: true };
});

describe("focused Metrics truthful states", () => {
  it("shows exact loading instead of broad live metrics", () => {
    mocks.focused = { ...mocks.focused, loading: true };
    render(<RuntimeMetricsView />);
    expect(screen.getByText(/Loading exact run metrics/i)).toBeTruthy();
    expect(screen.queryByText(/No runtime telemetry yet/i)).toBeNull();
  });

  it("shows exact unavailability without aggregate fallback", () => {
    mocks.focused = { entries: [], loading: false, error: "exact API offline", available: false };
    render(<RuntimeMetricsView />);
    expect(screen.getByText(/Run metrics unavailable/i)).toBeTruthy();
    expect(screen.getByText("exact API offline")).toBeTruthy();
  });

  it("shows authoritative empty even when broad live data exists", () => {
    render(<RuntimeMetricsView />);
    expect(screen.getByText(/No attributable runtime metrics/i)).toBeTruthy();
    expect(screen.queryByText("other")).toBeNull();
  });
});
