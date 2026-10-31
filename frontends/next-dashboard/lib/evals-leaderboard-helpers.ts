/**
 * Pure helpers for the Evals Leaderboard view.
 * No React, no side-effects — easy to unit test.
 */

export type EvalsSortMode = "top_score" | "biggest_gain" | "biggest_drop" | "newest";
export type EvalsFilterMode = "all" | "improved" | "regressed" | "baseline";

export interface ExperimentSummary {
  experiment_name: string;
  runs: number;
  latest_verdict: string;
  latest_pass_rate: number;
  avg_pass_rate: number;
  latest_avg_score: number;
  latest_timestamp: string;
  latest_run_id: string;
  latest_failed_cases: number;
  evaluators_used: string[];
  agent: { model_id?: string; system_prompt_snippet?: string };
  trend_direction: string;
  pass_rate_delta: number;
  regression_state: string;
  recent_pass_rates: number[];
  latest_status?: string;
  config_status: string;
}

export interface DashboardData {
  overview: {
    runs: number;
    experiments: number;
    saved_configs: number;
    failing_runs: number;
    regressions: number;
    avg_pass_rate: number;
  };
  experiments: ExperimentSummary[];
}

/**
 * Decompose an experiment name into chips: [model, technique, target].
 * DEFENSIVE: if split doesn't yield 2+ clean parts, return the full name as one chip.
 */
export function decomposeExperimentName(name: string): string[] {
  if (!name) return ["unnamed"];
  const parts = name.split("-").filter(Boolean);
  if (parts.length < 2) return [name];
  // Heuristic: treat as clean only if each part is purely alphanumeric/underscore
  const clean = parts.every((p) => /^[a-zA-Z0-9_]+$/.test(p));
  if (!clean) return [name];
  return parts;
}

/**
 * Derive improved/regressed counts from experiments list.
 */
export function deriveStatusCounts(experiments: ExperimentSummary[]): {
  improved: number;
  regressed: number;
  steady: number;
  baseline: number;
} {
  let improved = 0, regressed = 0, steady = 0, baseline = 0;
  for (const exp of experiments) {
    switch (exp.regression_state) {
      case "improved": improved++; break;
      case "regressed": regressed++; break;
      case "steady": steady++; break;
      default: baseline++; break;
    }
  }
  return { improved, regressed, steady, baseline };
}

/** Filter experiments by regression_state. */
export function filterExperiments(
  experiments: ExperimentSummary[],
  filter: EvalsFilterMode,
): ExperimentSummary[] {
  if (filter === "all") return experiments;
  return experiments.filter((e) => e.regression_state === filter);
}

/** Sort experiments by the given mode. Returns a new array. */
export function sortExperiments(
  experiments: ExperimentSummary[],
  mode: EvalsSortMode,
): ExperimentSummary[] {
  const sorted = [...experiments];
  switch (mode) {
    case "top_score":
      return sorted.sort((a, b) => b.latest_pass_rate - a.latest_pass_rate);
    case "biggest_gain":
      return sorted.sort((a, b) => (b.pass_rate_delta ?? 0) - (a.pass_rate_delta ?? 0));
    case "biggest_drop":
      return sorted.sort((a, b) => (a.pass_rate_delta ?? 0) - (b.pass_rate_delta ?? 0));
    case "newest":
      return sorted.sort((a, b) => (b.latest_timestamp || "").localeCompare(a.latest_timestamp || ""));
  }
}

export function completionLabel(exp: ExperimentSummary): string {
  if (exp.runs > 0 && !exp.latest_timestamp) return "Completed · time unavailable";
  if (exp.runs === 0 || exp.config_status === "saved_only") return "not run";
  return "Completed";
}

/** Case-insensitive search across experiment name, model, evaluators. */
export function matchesEvalsSearch(exp: ExperimentSummary, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    exp.experiment_name.toLowerCase().includes(q) ||
    (exp.agent?.model_id?.toLowerCase().includes(q) ?? false) ||
    exp.evaluators_used.some((e) => e.toLowerCase().includes(q))
  );
}
