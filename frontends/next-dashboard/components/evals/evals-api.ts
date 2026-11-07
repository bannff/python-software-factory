import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface Evaluator { name: string; description: string; requiresRubric: boolean }
/** `expected_output` is the key the server reads; anything else is silently ignored. */
export interface EvalCase { input: string; expected_output?: string }
export interface RunInput { cases: EvalCase[]; evaluator_names: string[]; experiment_name?: string; rubric?: string; model_id?: string }
export interface RunOutcome { cases: number; overallScore: number | null; passRate: number | null; errors: number }

export async function listEvaluators(): Promise<Evaluator[]> {
  const data = unwrapToolData(await callTool("evals_list_evaluators")) as { evaluators?: unknown } | null;
  const rows = Array.isArray(data?.evaluators) ? data.evaluators : [];
  return rows.flatMap((r: Record<string, unknown>) => typeof r?.name === "string"
    ? [{ name: r.name, description: typeof r.description === "string" ? r.description : "", requiresRubric: r.requires_rubric === true }] : []);
}

/** Sends only what the person filled in, so server defaults (model, prompt) stay in charge. */
export async function runExperiment(input: RunInput): Promise<RunOutcome> {
  const args: Record<string, unknown> = { ...input };
  for (const key of ["experiment_name", "rubric", "model_id"] as const) if (!input[key]?.trim()) delete args[key];
  const data = unwrapToolData(await callTool("evals_run_experiment", args)) as Record<string, unknown> | null;
  const summary = (data?.summary && typeof data.summary === "object" ? data.summary : {}) as Record<string, unknown>;
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  return {
    cases: Array.isArray(data?.case_results) ? data.case_results.length : input.cases.length,
    overallScore: num(summary.overall_score), passRate: num(summary.pass_rate), errors: num(summary.evaluation_errors) ?? 0,
  };
}

const MODELS = "Evaluation models aren't set up on this server, so the run couldn't be scored. Ask an operator to configure them.";
const FAILURES: [RegExp, string][] = [
  [/eval_model_unavailable|tool_execution_failed/, MODELS],
];

export function runFailure(cause: unknown): string {
  const reason = errorReason(cause) ?? "";
  const known = FAILURES.find(([pattern]) => pattern.test(reason));
  return known ? known[1] : withReason("The run could not start.", reason || undefined);
}
