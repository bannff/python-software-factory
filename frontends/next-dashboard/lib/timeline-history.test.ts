import test from "node:test";
import assert from "node:assert/strict";

const { mapTimelineHistoryRows } = await import(
  new URL("./timeline-history.ts", import.meta.url).href,
);

// Migrated to flat-dict row shape under bd python-factory-c39g
// (graph_list_recent_tool_invocations replaces graph_query +
// TIMELINE_HISTORY_QUERY). Rows are now keyed dicts, not positional.

test("mapTimelineHistoryRows preserves workflow_run_id for Timeline grouping", () => {
  const entries = mapTimelineHistoryRows([
    {
      tool_name: "agent_reason",
      brick: "agent",
      success: true,
      latency_ms: 12.5,
      created_at: "2026-05-12T12:00:00Z",
      error: null,
      workflow_run_id: "run-99",
      args_summary: '{"task":"x"}',
      caller: "ag_ui",
      result_summary: '{"text":"ok"}',
      session_id: "session-42",
      session_agent_id: "agent-red",
      session_principal_id: "principal-7",
    },
  ]);

  assert.equal(entries.length, 1);
  assert.equal(entries[0]?.workflow_run_id, "run-99");
  assert.equal(entries[0]?.session_id, "session-42");
  assert.equal(entries[0]?.agent_id, "agent-red");
  assert.equal(entries[0]?.principal_id, "principal-7");
  assert.equal(entries[0]?.status, "completed");
  assert.equal(entries[0]?.detail, "agent");
  assert.deepEqual(entries[0]?.args_summary, { task: "x" });
  assert.deepEqual(entries[0]?.result_summary, { text: "ok" });
  assert.equal(entries[0]?.caller, "ag_ui");
});

test("mapTimelineHistoryRows handles empty rows", () => {
  const entries = mapTimelineHistoryRows([]);
  assert.equal(entries.length, 0);
});

test("mapTimelineHistoryRows falls back through principal sources", () => {
  const entries = mapTimelineHistoryRows([
    {
      tool_name: "kb_search",
      success: true,
      // No session join — session_principal_id absent.
      principal_id: "principal-fallback",
    },
  ]);
  assert.equal(entries[0]?.principal_id, "principal-fallback");
});
