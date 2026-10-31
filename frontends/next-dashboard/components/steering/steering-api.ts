import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface SteeringDocument {
  id: string;
  title: string;
  sha256: string;
  content?: string;
}

function document(raw: unknown): SteeringDocument | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.id !== "string" || typeof value.title !== "string" || typeof value.sha256 !== "string") return null;
  return { id: value.id, title: value.title, sha256: value.sha256,
    ...(typeof value.content === "string" ? { content: value.content } : {}) };
}

export async function listSteering(): Promise<SteeringDocument[]> {
  const data = unwrapToolData(await callTool("agent_list_steering")) as { documents?: unknown };
  return Array.isArray(data?.documents)
    ? data.documents.map(document).filter((row): row is SteeringDocument => row !== null) : [];
}

export async function readSteering(id: string): Promise<Required<SteeringDocument>> {
  const row = document(unwrapToolData(await callTool("agent_read_steering", { document_id: id })));
  if (!row || row.content === undefined) throw new Error("Steering document unavailable.");
  return row as Required<SteeringDocument>;
}

export async function saveSteering(input: {
  id: string; content: string; expectedSha256?: string;
}): Promise<Required<SteeringDocument>> {
  const updating = Boolean(input.expectedSha256);
  const name = updating ? "agent_update_steering" : "agent_create_steering";
  const args: Record<string, unknown> = { document_id: input.id, content: input.content };
  if (input.expectedSha256) args.expected_sha256 = input.expectedSha256;
  const data = unwrapToolData(await callTool(name, args)) as { document?: unknown };
  const row = document(data?.document);
  if (!row || row.content === undefined) throw new Error("Steering document was not saved.");
  return row as Required<SteeringDocument>;
}

export async function deleteSteering(id: string, expectedSha256: string): Promise<void> {
  const data = unwrapToolData(
    await callTool("agent_delete_steering", { document_id: id, expected_sha256: expectedSha256 }),
  ) as { deleted?: unknown };
  if (data?.deleted !== true) throw new Error("Steering document was not deleted.");
}
