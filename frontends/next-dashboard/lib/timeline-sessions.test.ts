import test from "node:test";
import assert from "node:assert/strict";

import type { SessionGroup } from "./timeline-sessions";
import type { TimelineEntry } from "@/lib/types";

const { groupTimelineSessions } = await import(
  new URL("./timeline-sessions.ts", import.meta.url).href,
);

test("groupTimelineSessions keeps mixed history separated by workflow_run_id", () => {
  const groups = groupTimelineSessions([
    {
      id: "hist-0",
      type: "tool_call",
      title: "agent_reason",
      status: "completed",
      timestamp: Date.parse("2026-05-12T12:00:00Z"),
      workflow_run_id: "run-a",
      agent_id: "agent-red",
      principal_id: "principal-7",
    },
    {
      id: "hist-1",
      type: "tool_call",
      title: "cache_get",
      status: "completed",
      timestamp: Date.parse("2026-05-12T12:00:02Z"),
      workflow_run_id: "run-a",
      agent_id: "agent-red",
      principal_id: "principal-7",
    },
    {
      id: "hist-2",
      type: "tool_call",
      title: "graph_query",
      status: "failed",
      timestamp: Date.parse("2026-05-12T12:00:01Z"),
      workflow_run_id: "run-b",
    },
    {
      id: "hist-3",
      type: "tool_call",
      title: "legacy_tool",
      status: "completed",
      timestamp: Date.parse("2026-05-12T11:00:00Z"),
    },
  ]);

  assert.equal(groups.length, 3);

  const runA = groups.find((group: SessionGroup) => group.workflowRunId === "run-a");
  const runB = groups.find((group: SessionGroup) => group.workflowRunId === "run-b");
  const fallback = groups.find((group: SessionGroup) => group.workflowRunId === undefined);

  assert.ok(runA);
  assert.equal(runA.toolCount, 2);
  assert.equal(runA.errorCount, 0);
  assert.deepEqual(runA.agentIds, ["agent-red"]);
  assert.deepEqual(runA.principalIds, ["principal-7"]);
  assert.deepEqual(
    runA.entries.map((entry: TimelineEntry) => entry.id),
    ["hist-1", "hist-0"],
  );

  assert.ok(runB);
  assert.equal(runB.toolCount, 1);
  assert.equal(runB.errorCount, 1);
  assert.equal(runB.entries[0]?.id, "hist-2");

  assert.ok(fallback);
  assert.equal(fallback.toolCount, 1);
  assert.equal(fallback.entries[0]?.id, "hist-3");
});