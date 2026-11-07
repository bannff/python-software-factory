import { callTool } from "@/lib/api";
import { fetchToolCatalog } from "@/lib/tool-catalog";
import { unwrapToolData } from "@/lib/tool-result-data";

function authoringResult(raw: unknown): Record<string, unknown> {
  const data = unwrapToolData(raw) as { success?: boolean; result?: unknown } | undefined;
  if (!data?.success || !data.result || typeof data.result !== "object") {
    throw new Error("Agent template operation failed.");
  }
  const result = data.result as Record<string, unknown>;
  if (result.ok === false) throw new Error(String(result.details || result.error || "Operation failed"));
  return result;
}


export interface UserTemplate {
  id: string;
  /** Source persona id when this template was forked; null for hand-authored ones. */
  forkedFrom: string | null;
}

export async function listUserTemplates(): Promise<UserTemplate[]> {
  const result = authoringResult(await callTool("agent_list_config_items", { kind: "agent" }));
  if (!Array.isArray(result.items)) return [];
  return result.items.flatMap((item): UserTemplate[] => typeof item?.id === "string"
    ? [{ id: item.id, forkedFrom: typeof item.forked_from === "string" ? item.forked_from : null }] : []);
}

/** The agent ID rule the backend publishes on `agent_fork_agent`'s input schema
 * (create takes an opaque config dict, so it states none). Null when absent. */
export async function getTemplateIdPattern(): Promise<string | null> {
  const { tools } = await fetchToolCatalog();
  const fork = tools.find((tool) => tool.qualified_name === "agent_fork_agent");
  const pattern = fork?.input_schema?.properties?.new_agent_id?.pattern;
  return typeof pattern === "string" ? pattern : null;
}

export async function readUserTemplate(id: string): Promise<Record<string, unknown>> {
  const result = authoringResult(await callTool("agent_read_config", {
    kind: "agent", item_id: id,
  }));
  if (!result.config || typeof result.config !== "object") throw new Error("Template unavailable.");
  return result.config as Record<string, unknown>;
}

export async function saveUserTemplate(config: Record<string, unknown>): Promise<void> {
  authoringResult(await callTool("agent_create_agent", { config }));
}

export async function deleteUserTemplate(id: string): Promise<void> {
  authoringResult(await callTool("agent_delete_agent", { agent_id: id }));
}

/** Row 33 (feature-map): copy any persona (built-in or user) to a new
 * id the owner can freely edit. Returns the new template's id. */
export async function forkTemplate(sourceId: string, newId: string): Promise<string> {
  const result = authoringResult(await callTool("agent_fork_agent", {
    source_agent_id: sourceId, new_agent_id: newId,
  }));
  return String(result.id ?? newId);
}

/** Row 33 (feature-map): discard a fork's local edits, restoring it to
 * its source persona's current definition. Fails with `not_a_fork` if
 * this id was never created via `forkTemplate`. */
export async function resetTemplate(id: string): Promise<void> {
  authoringResult(await callTool("agent_reset_agent", { agent_id: id }));
}
