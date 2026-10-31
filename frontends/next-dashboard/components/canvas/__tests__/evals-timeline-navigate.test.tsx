import { fireEvent, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockUseToolData = vi.fn();
vi.mock("@companion-x/shared-renderer", () => ({ useToolData: (...args: unknown[]) => mockUseToolData(...args) }));
vi.mock("@/lib/hooks/use-focused-eval-result", () => ({
  useFocusedEvalResult: () => ({ loading: false, error: null, found: false, result: null }),
}));

import EvalsLeaderboardView from "../evals-leaderboard-view";
import { WorkbenchProvider } from "@/lib/workbench-context";

const RUN_ID = "run-abc123-full-identifier";
const DASHBOARD = {
  overview: { runs: 1, experiments: 1, saved_configs: 1, failing_runs: 0, regressions: 0, avg_pass_rate: 0.8 },
  experiments: [{ experiment_name: "idor-detect-pets", runs: 1, latest_verdict: "PASS", latest_pass_rate: 0.8, avg_pass_rate: 0.8, latest_avg_score: 0.85, latest_timestamp: "2026-06-20T10:00:00Z", latest_run_id: RUN_ID, latest_failed_cases: 0, evaluators_used: ["output"], agent: { model_id: "claude" }, trend_direction: "up", pass_rate_delta: 0.1, regression_state: "improved", recent_pass_rates: [0.7, 0.8], config_status: "saved" }],
};

beforeEach(() => {
  mockUseToolData.mockReset();
  window.history.replaceState({}, "", "/?keep=1");
});

describe("Evals run navigation", () => {
  it("sets central full-ID focus then navigates to Timeline", () => {
    const onNavigate = vi.fn();
    mockUseToolData.mockReturnValue({ data: DASHBOARD, loading: false, error: null, refetch: vi.fn() });
    const { container } = render(<WorkbenchProvider><EvalsLeaderboardView onNavigate={onNavigate} /></WorkbenchProvider>);
    fireEvent.click(container.querySelector("button[aria-label^='Toggle details']") as HTMLElement);
    const chip = container.querySelector("button[aria-label^='Filter by run']") as HTMLElement;
    fireEvent.click(chip);
    expect(new URL(window.location.href).searchParams.get("run")).toBe(RUN_ID);
    expect(new URL(window.location.href).searchParams.get("keep")).toBe("1");
    expect(onNavigate).toHaveBeenCalledWith("timeline-v2");
  });
});
