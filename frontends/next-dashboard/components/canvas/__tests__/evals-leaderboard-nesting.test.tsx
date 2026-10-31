import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const mockUseToolData = vi.fn();

vi.mock("@companion-x/shared-renderer", () => ({
  useToolData: (...args: unknown[]) => mockUseToolData(...args),
}));

import { EvalsLeaderboardAggregate } from "../evals-leaderboard-aggregate";

const MOCK_DASHBOARD = {
  overview: { runs: 5, experiments: 2, saved_configs: 1, failing_runs: 1, regressions: 1, avg_pass_rate: 0.7 },
  experiments: [
    {
      experiment_name: "idor-detect-pets",
      runs: 3,
      latest_verdict: "PASS",
      latest_pass_rate: 0.8,
      avg_pass_rate: 0.75,
      latest_avg_score: 0.85,
      latest_timestamp: "2026-06-20T10:00:00Z",
      latest_run_id: "run-abc123",
      latest_failed_cases: 1,
      evaluators_used: ["output"],
      agent: { model_id: "anthropic.claude-sonnet-4-5" },
      trend_direction: "up",
      pass_rate_delta: 0.1,
      regression_state: "improved",
      recent_pass_rates: [0.6, 0.7, 0.8],
      config_status: "saved",
    },
    {
      experiment_name: "sqli-scanner",
      runs: 2,
      latest_verdict: "FAIL",
      latest_pass_rate: 0.4,
      avg_pass_rate: 0.5,
      latest_avg_score: 0.45,
      latest_timestamp: "2026-06-19T10:00:00Z",
      latest_run_id: "run-def456",
      latest_failed_cases: 3,
      evaluators_used: ["output", "trajectory"],
      agent: { model_id: "anthropic.claude-haiku-3" },
      trend_direction: "down",
      pass_rate_delta: -0.2,
      regression_state: "regressed",
      recent_pass_rates: [0.6, 0.4],
      config_status: "ad_hoc",
    },
  ],
};

describe("EvalsLeaderboardView - no nested buttons (hydration guard)", () => {
  beforeEach(() => {
    mockUseToolData.mockReset();
  });

  it("does not nest button inside button when rows are rendered", () => {
    mockUseToolData.mockReturnValue({ data: MOCK_DASHBOARD, loading: false, error: null, refetch: vi.fn() });

    const { container } = render(<EvalsLeaderboardAggregate onRunSelect={vi.fn()} />);
    const nestedButtons = container.querySelectorAll("button button");
    expect(nestedButtons.length).toBe(0);
  });

  it("renders multiple experiment rows", () => {
    mockUseToolData.mockReturnValue({ data: MOCK_DASHBOARD, loading: false, error: null, refetch: vi.fn() });

    const { container } = render(<EvalsLeaderboardAggregate onRunSelect={vi.fn()} />);
    // 2 experiments → 2 Collapsible triggers + sort buttons (4) + filter buttons (4) + cross-link chips (2) = many buttons, none nested
    const allButtons = container.querySelectorAll("button");
    expect(allButtons.length).toBeGreaterThan(4);
    expect(container.querySelectorAll("button button").length).toBe(0);
  });

  it("shows loading state", () => {
    mockUseToolData.mockReturnValue({ data: null, loading: true, error: null, refetch: vi.fn() });
    const { container } = render(<EvalsLeaderboardAggregate onRunSelect={vi.fn()} />);
    expect(container.querySelector(".animate-spin")).not.toBeNull();
  });

  it("shows empty state when no experiments", () => {
    mockUseToolData.mockReturnValue({ data: { overview: {}, experiments: [] }, loading: false, error: null, refetch: vi.fn() });
    const { container } = render(<EvalsLeaderboardAggregate onRunSelect={vi.fn()} />);
    expect(container.textContent).toContain("No experiments yet");
  });
});
