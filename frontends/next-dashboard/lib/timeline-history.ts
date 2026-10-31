import type { TimelineEntry } from "@/lib/types";

// Flat row shape returned by graph_list_recent_tool_invocations
// (bd python-factory-c39g). Each row is a dict, NOT a Cypher
// positional array.

function parseJsonSummary(value: unknown): Record<string, unknown> | undefined {
  if (value == null || value === "") return undefined;
  if (typeof value === "object" && value !== null) {
    return value as Record<string, unknown>;
  }
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as Record<string, unknown>;
    } catch {
      return undefined;
    }
  }
  return undefined;
}

function firstNonEmptyString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value !== "") return value;
  }
  return undefined;
}

export function mapTimelineHistoryRows(
  rows: Record<string, unknown>[],
): TimelineEntry[] {
  return rows.map((row, index) => {
    const tool_name = String(row.tool_name ?? "unknown");
    const brick = row.brick != null ? String(row.brick) : undefined;
    const raw_success = row.success;
    const success =
      raw_success === true || raw_success === 1 || raw_success === "true";
    const latency_ms = row.latency_ms != null ? Number(row.latency_ms) : undefined;
    const created_at_raw = row.created_at;
    const error_raw = row.error;
    const error =
      error_raw != null && error_raw !== "" ? String(error_raw) : undefined;
    const wf_run_raw = row.workflow_run_id;
    const workflow_run_id =
      wf_run_raw != null && wf_run_raw !== "" ? String(wf_run_raw) : undefined;
    const args_summary = parseJsonSummary(row.args_summary);
    const caller_raw = row.caller;
    const caller =
      caller_raw != null && caller_raw !== "" ? String(caller_raw) : undefined;
    const result_summary = parseJsonSummary(row.result_summary);
    const session_id = firstNonEmptyString(row.session_id);
    const agent_id = firstNonEmptyString(row.session_agent_id);
    const principal_id = firstNonEmptyString(
      row.session_principal_id,
      row.principal_id,
    );

    let created_at: number;
    if (created_at_raw == null) {
      created_at = Date.now() - index * 1000;
    } else if (typeof created_at_raw === "string") {
      const parsed = Date.parse(created_at_raw);
      created_at = Number.isNaN(parsed) ? Date.now() - index * 1000 : parsed;
    } else {
      const parsed = Number(created_at_raw);
      created_at = Number.isNaN(parsed) ? Date.now() - index * 1000 : parsed;
    }

    return {
      id: `hist-${index}`,
      type: "tool_call",
      title: tool_name,
      status: success ? "completed" : "failed",
      timestamp: created_at,
      duration: latency_ms,
      detail: brick,
      error,
      workflow_run_id,
      session_id,
      agent_id,
      principal_id,
      args_summary,
      caller,
      result_summary,
    };
  });
}
