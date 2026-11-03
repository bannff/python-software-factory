import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface Dataset {
  dataset_id: string; uri: string; manifest_uri: string; digest: string;
  view_name: string; view_schema_version: string; description: string; revision: number;
}
export interface DatasetInput {
  name: string; uri: string; manifest_uri: string; digest: string;
  view_name: string; view_schema_version: string; description: string;
}

const str = (v: unknown) => (typeof v === "string" ? v : "");

function rowFrom(raw: unknown): Dataset | null {
  const v = raw as Record<string, unknown> | null;
  if (!v || typeof v.dataset_id !== "string" || typeof v.revision !== "number") return null;
  return { dataset_id: v.dataset_id, uri: str(v.uri), manifest_uri: str(v.manifest_uri), digest: str(v.digest),
    view_name: str(v.view_name), view_schema_version: str(v.view_schema_version),
    description: str(v.description), revision: v.revision };
}

export async function listDatasets(): Promise<Dataset[]> {
  const data = unwrapToolData(await callTool("ml_list_datasets")) as { datasets?: unknown };
  return Array.isArray(data?.datasets) ? data.datasets.map(rowFrom).filter((d): d is Dataset => d !== null) : [];
}
export async function registerDataset(input: DatasetInput): Promise<void> {
  unwrapToolData(await callTool("ml_register_dataset", { ...input }));
}
export async function updateDataset(datasetId: string, description: string, expectedRevision: number): Promise<void> {
  unwrapToolData(await callTool("ml_update_dataset",
    { dataset_id: datasetId, description, expected_revision: expectedRevision }));
}
export async function deleteDataset(datasetId: string): Promise<void> {
  unwrapToolData(await callTool("ml_delete_dataset", { dataset_id: datasetId }));
}
