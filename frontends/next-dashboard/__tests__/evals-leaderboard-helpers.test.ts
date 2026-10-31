import { describe, it, expect } from "vitest";
import {
  decomposeExperimentName,
  deriveStatusCounts,
  sortExperiments,
  filterExperiments,
  matchesEvalsSearch,
  type ExperimentSummary,
} from "@/lib/evals-leaderboard-helpers";

const makeExp = (overrides: Partial<ExperimentSummary> = {}): ExperimentSummary => ({
  experiment_name: "idor-detect-pets",
  runs: 3,
  latest_verdict: "PASS",
  latest_pass_rate: 0.8,
  avg_pass_rate: 0.75,
  latest_avg_score: 0.85,
  latest_timestamp: "2026-06-20T10:00:00Z",
  latest_run_id: "run-abc",
  latest_failed_cases: 1,
  evaluators_used: ["output"],
  agent: { model_id: "anthropic.claude-sonnet-4-5", system_prompt_snippet: "You are..." },
  trend_direction: "up",
  pass_rate_delta: 0.1,
  regression_state: "improved",
  recent_pass_rates: [0.6, 0.7, 0.8],
  config_status: "saved",
  ...overrides,
});

describe("decomposeExperimentName", () => {
  it("splits clean hyphenated names into chips", () => {
    expect(decomposeExperimentName("idor-detect-pets")).toEqual(["idor", "detect", "pets"]);
  });

  it("returns full name as single chip when split yields one part", () => {
    expect(decomposeExperimentName("singleword")).toEqual(["singleword"]);
  });

  it("defensive fallback for names with special chars", () => {
    expect(decomposeExperimentName("my experiment (v2)")).toEqual(["my experiment (v2)"]);
  });

  it("handles empty string", () => {
    expect(decomposeExperimentName("")).toEqual(["unnamed"]);
  });

  it("handles names with only hyphens cleanly", () => {
    expect(decomposeExperimentName("a-b")).toEqual(["a", "b"]);
  });
});

describe("deriveStatusCounts", () => {
  it("counts each regression_state", () => {
    const exps = [
      makeExp({ regression_state: "improved" }),
      makeExp({ regression_state: "regressed" }),
      makeExp({ regression_state: "improved" }),
      makeExp({ regression_state: "baseline" }),
      makeExp({ regression_state: "steady" }),
    ];
    expect(deriveStatusCounts(exps)).toEqual({ improved: 2, regressed: 1, steady: 1, baseline: 1 });
  });

  it("treats unknown states as baseline", () => {
    const exps = [makeExp({ regression_state: "unknown_state" })];
    expect(deriveStatusCounts(exps)).toEqual({ improved: 0, regressed: 0, steady: 0, baseline: 1 });
  });
});

describe("sortExperiments", () => {
  const a = makeExp({ experiment_name: "a", latest_pass_rate: 0.9, pass_rate_delta: 0.3, latest_timestamp: "2026-06-20" });
  const b = makeExp({ experiment_name: "b", latest_pass_rate: 0.5, pass_rate_delta: -0.2, latest_timestamp: "2026-06-22" });
  const c = makeExp({ experiment_name: "c", latest_pass_rate: 0.7, pass_rate_delta: 0.0, latest_timestamp: "2026-06-21" });

  it("top_score sorts by latest_pass_rate desc", () => {
    const result = sortExperiments([b, c, a], "top_score");
    expect(result.map((e) => e.experiment_name)).toEqual(["a", "c", "b"]);
  });

  it("biggest_gain sorts by pass_rate_delta desc", () => {
    const result = sortExperiments([b, c, a], "biggest_gain");
    expect(result.map((e) => e.experiment_name)).toEqual(["a", "c", "b"]);
  });

  it("biggest_drop sorts by pass_rate_delta asc", () => {
    const result = sortExperiments([a, c, b], "biggest_drop");
    expect(result.map((e) => e.experiment_name)).toEqual(["b", "c", "a"]);
  });

  it("newest sorts by latest_timestamp desc", () => {
    const result = sortExperiments([a, c, b], "newest");
    expect(result.map((e) => e.experiment_name)).toEqual(["b", "c", "a"]);
  });
});

describe("filterExperiments", () => {
  const exps = [
    makeExp({ regression_state: "improved" }),
    makeExp({ regression_state: "regressed" }),
    makeExp({ regression_state: "baseline" }),
  ];

  it("all returns everything", () => {
    expect(filterExperiments(exps, "all")).toHaveLength(3);
  });

  it("improved filters correctly", () => {
    expect(filterExperiments(exps, "improved")).toHaveLength(1);
    expect(filterExperiments(exps, "improved")[0].regression_state).toBe("improved");
  });

  it("regressed filters correctly", () => {
    expect(filterExperiments(exps, "regressed")).toHaveLength(1);
  });
});

describe("matchesEvalsSearch", () => {
  const exp = makeExp();

  it("matches experiment name", () => {
    expect(matchesEvalsSearch(exp, "idor")).toBe(true);
  });

  it("matches model_id", () => {
    expect(matchesEvalsSearch(exp, "claude")).toBe(true);
  });

  it("matches evaluator", () => {
    expect(matchesEvalsSearch(exp, "output")).toBe(true);
  });

  it("no match returns false", () => {
    expect(matchesEvalsSearch(exp, "xyz123")).toBe(false);
  });

  it("empty query matches everything", () => {
    expect(matchesEvalsSearch(exp, "")).toBe(true);
  });
});
