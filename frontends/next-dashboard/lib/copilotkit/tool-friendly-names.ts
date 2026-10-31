/**
 * Friendly display names + categorisation for MCP tool identifiers.
 *
 * Used by the chat header (bd-de2h / D5) to avoid leaking infra-y tool
 * IDs like ``ui_start_session`` into the user-visible status, and by
 * the wildcard tool-card renderer (bd-f849 / D4) to spot frontend tools
 * (``fe_`` prefix) so they get a violet accent + monitor icon instead
 * of looking identical to backend bricks.
 */

const INFRASTRUCTURE_TOOLS: ReadonlySet<string> = new Set([
  // Session bookkeeping the chat agent does on every turn — uninteresting
  // to surface to a human.
  "ui_start_session",
  "ui_ui_start_session",
  "ui_end_session",
  "ui_ui_end_session",
  "ui_session_keepalive",
  "graph_get_views",
  "telemetry_get_views",
  "telemetry_record_view_render",
  "graph_list_recent_tool_invocations",
  "graph_get_session_metadata",
  // ``get_stats`` is the gateway's own meta-tool, called every turn by
  // companion-x to populate the inspector. It says nothing about what
  // the agent is doing.
  "get_stats",
]);

const FRIENDLY_LABELS: ReadonlyMap<string, string> = new Map([
  ["kb_search", "Knowledge search"],
  ["kb_kb_search", "Knowledge search"],
  ["cache_get", "Cache lookup"],
  ["cache_cache_get", "Cache lookup"],
  ["graph_query", "Graph query"],
  ["graph_graph_query", "Graph query"],
  ["memory_store", "Save to memory"],
  ["memory_memory_store", "Save to memory"],
  ["memory_retrieve", "Recall memory"],
  ["memory_memory_retrieve", "Recall memory"],
  ["fe_navigate_canvas", "Switch view"],
  ["fe_navigate_artifacts", "Open artifacts"],
  ["fe_focus_run", "Focus workflow run"],
]);

export interface FriendlyToolMeta {
  /** Human label, falling back to a Title-cased version of the raw id. */
  label: string;
  /** True when the tool is plumbing the user shouldn't see in the header. */
  isInfrastructure: boolean;
  /** True when executed in the browser (CopilotKit FE tool round-trip). */
  isFrontend: boolean;
}

function titleCase(name: string): string {
  return name
    .replace(/^(fe|ui|kb|aws|ml|rl)_/, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function describeTool(name: string): FriendlyToolMeta {
  const trimmed = (name ?? "").trim();
  return {
    label: FRIENDLY_LABELS.get(trimmed) ?? titleCase(trimmed || "tool"),
    isInfrastructure: INFRASTRUCTURE_TOOLS.has(trimmed),
    isFrontend: trimmed.startsWith("fe_"),
  };
}

/**
 * Pick the most recent live-tool-stream entry that is *interesting*
 * for the chat header (skip session keepalives, telemetry pings, etc.).
 * Returns null when nothing on the stream rises above noise.
 */
export function pickHeaderTool<T extends { title: string }>(
  entries: ReadonlyArray<T>,
): { entry: T; meta: FriendlyToolMeta } | null {
  for (const entry of entries) {
    const meta = describeTool(entry.title);
    if (!meta.isInfrastructure) return { entry, meta };
  }
  return null;
}
