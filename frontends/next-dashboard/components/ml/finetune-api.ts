import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface FineTuneJob {
  id: string; status: string; method: string; base_model: string; loss: number | null; checkpoints: number | null;
}
export interface FineTuneMethod { name: string; description: string }
export interface JobInput {
  method: string; base_model: string; dataset_uri: string; manifest_uri: string;
  dataset_digest: string; view_name: string; view_schema_version: string;
  /** A registered dataset; when set the five explicit dataset fields are not sent. */
  dataset_id?: string;
}

function jobFrom(raw: unknown): FineTuneJob | null {
  if (!raw || typeof raw !== "object") return null;
  const v = raw as Record<string, unknown>;
  if (typeof v.id !== "string" || typeof v.status !== "string") return null;
  return { id: v.id, status: v.status, method: typeof v.method === "string" ? v.method : "",
    base_model: typeof v.base_model === "string" ? v.base_model : "",
    loss: typeof v.loss === "number" ? v.loss : null,
    checkpoints: typeof v.checkpoints === "number" ? v.checkpoints : null };
}

export async function listJobs(): Promise<FineTuneJob[]> {
  const data = unwrapToolData(await callTool("ml_list_finetuning_jobs")) as { jobs?: unknown };
  return Array.isArray(data?.jobs) ? data.jobs.map(jobFrom).filter((j): j is FineTuneJob => j !== null) : [];
}

export async function listMethods(): Promise<FineTuneMethod[]> {
  const data = unwrapToolData(await callTool("ml_list_finetuning_methods")) as { methods?: unknown };
  return Array.isArray(data?.methods) ? data.methods.flatMap((m): FineTuneMethod[] => {
    const v = m as Record<string, unknown>;
    return typeof v?.name === "string" ? [{ name: v.name, description: typeof v.description === "string" ? v.description : "" }] : [];
  }) : [];
}

export async function createJob(input: JobInput): Promise<void> {
  const { dataset_id, ...explicit } = input;
  unwrapToolData(await callTool("ml_create_finetuning_job", dataset_id
    ? { method: input.method, base_model: input.base_model, dataset_id }
    : explicit));
}
export async function startJob(jobId: string): Promise<void> {
  unwrapToolData(await callTool("ml_start_finetuning_job", { job_id: jobId }));
}
export async function stopJob(jobId: string): Promise<void> {
  unwrapToolData(await callTool("ml_stop_finetuning_job", { job_id: jobId }));
}
