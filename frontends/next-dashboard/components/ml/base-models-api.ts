import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface BaseModel { name: string; model_id: string; description: string; recommended_method: string }

const str = (v: unknown) => (typeof v === "string" ? v : "");

export async function listBaseModels(): Promise<BaseModel[]> {
  const data = unwrapToolData(await callTool("ml_list_base_models")) as { models?: unknown };
  return Array.isArray(data?.models) ? data.models.flatMap((m): BaseModel[] => {
    const v = m as Record<string, unknown>;
    return typeof v?.name === "string"
      ? [{ name: v.name, model_id: str(v.model_id), description: str(v.description), recommended_method: str(v.recommended_method) }]
      : [];
  }) : [];
}
export async function registerBaseModel(m: BaseModel): Promise<void> {
  unwrapToolData(await callTool("ml_register_base_model", { ...m }));
}
export async function updateBaseModel(m: BaseModel): Promise<void> {
  unwrapToolData(await callTool("ml_update_base_model", { ...m }));
}
export async function deleteBaseModel(name: string): Promise<void> {
  unwrapToolData(await callTool("ml_delete_base_model", { name }));
}

/** Typed refusals and the authoring switch in words; anything else keeps the server's reason. */
export function baseModelFailure(prose: string, cause: unknown): string {
  const reason = errorReason(cause) ?? "";
  if (/authoring tools disabled/i.test(reason)) return "Base-model editing is turned off on this server.";
  if (reason.includes("base_model_in_use")) return "This base model is used by a fine-tuning job. Delete that job first.";
  if (reason.includes("base_model_not_found")) return "This base model no longer exists.";
  return withReason(prose, reason || undefined);
}
