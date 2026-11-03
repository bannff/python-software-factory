import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface TrainInput { model_type: string; X_uri: string; y_uri: string; experiment_name: string }
export interface TrainResult { job_id: string; status: string; metrics: Record<string, number | string> }

/** The model types the server supports, when it says so; empty means the UI must not guess. */
export async function listModelTypes(): Promise<string[]> {
  const data = unwrapToolData(await callTool("ml_get_capabilities")) as { timeseries_model_types?: unknown } | null;
  const types = data?.timeseries_model_types;
  return Array.isArray(types) ? types.filter((t): t is string => typeof t === "string") : [];
}

export async function trainModel(input: TrainInput): Promise<TrainResult> {
  const data = unwrapToolData(await callTool("ml_train_timeseries", { ...input })) as Record<string, unknown> | null;
  const metrics = (data?.metrics && typeof data.metrics === "object" ? data.metrics : {}) as Record<string, number | string>;
  return { job_id: typeof data?.job_id === "string" ? data.job_id : "", status: typeof data?.status === "string" ? data.status : "", metrics };
}

/** Typed training failures in plain words, with the older untyped strings kept as a fallback. */
const FAILURES: [RegExp, string][] = [
  [/timeseries_model_type_invalid|is not a valid TimeSeriesModelType/i, "That model type isn't available on this server."],
  [/timeseries_config_invalid/, "Those training settings aren't valid."],
  [/training_data_unreadable/, "Training could not run. Check that both dataset locations exist and can be read, then try again."],
  [/tool_execution_failed/, "Training could not run on the server. The data may be unreadable or the server may need setup; the server log has the details."],
  [/training_failed/, "Training failed while running. Try again, or check the server log."],
];

export function trainFailure(cause: unknown): string {
  const reason = errorReason(cause) ?? "";
  const known = FAILURES.find(([pattern]) => pattern.test(reason));
  return known ? known[1] : withReason("Training could not start.", reason || undefined);
}
