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

/** Training raises on unreadable data (opaque) and leaks a Python enum message for a bad type; say it plainly. */
export function trainFailure(cause: unknown): string {
  const reason = errorReason(cause) ?? "";
  if (/is not a valid TimeSeriesModelType/i.test(reason)) return "That model type isn't available on this server.";
  if (/tool_execution_failed/.test(reason)) return "Training could not run. Check that both dataset locations exist and can be read, then try again.";
  return withReason("Training could not start.", reason || undefined);
}
