import { describe, expect, it } from "vitest";
import { reduceRunActivity } from "@/lib/run-activity";
import type { TimelineEntry } from "@/lib/types";

function event(type: string, timestamp: number, meta: Record<string, unknown>): TimelineEntry {
  return { id: `${type}-${timestamp}`, type: "swarm_event", title: type, status: "running", timestamp, workflow_run_id: String(meta.run_id ?? ""), swarmEventType: type, swarmMeta: meta };
}

describe("run activity lifecycle reducer", () => {
  it("reduces oldest-to-newest even when the singleton buffer is newest-first", () => {
    const rows = [
      event("graph.node_stop", 4, { run_id: "r1", node_id: "a1" }),
      event("graph.node_start", 3, { run_id: "r1", node_id: "a1" }),
      event("graph.launched", 2, { run_id: "r1" }),
      event("graph.completed", 5, { run_id: "r1" }),
    ];
    expect(reduceRunActivity(rows)).toEqual({ runs: false, agents: false, invocations: false });
  });

  it("closes canonical Workflow activity for every terminal outcome", () => {
    for (const terminal of [
      "workflow.run_succeeded", "workflow.run_failed", "workflow.run_cancelled",
    ]) {
      const rows = [
        event("workflow.run_started", 1, { run_id: "wfr:v1:durable" }),
        event(terminal, 2, { run_id: "wfr:v1:durable" }),
      ];
      expect(reduceRunActivity(rows)).toEqual({ runs: false, agents: false, invocations: false });
    }
  });

  it("closes descendant activity when a run reaches a terminal state", () => {
    const rows = [
      event("graph.launched", 1, { run_id: "r1" }),
      event("graph.node_start", 2, { run_id: "r1", node_id: "a1" }),
      event("swarm.tool_start", 3, { run_id: "r1", node_id: "a1", invocation_id: "i1" }),
      event("graph.failed", 4, { run_id: "r1" }),
    ];
    expect(reduceRunActivity(rows)).toEqual({ runs: false, agents: false, invocations: false });
  });

  it("reconciles independent run, agent, and invocation keys without counts", () => {
    const rows = [
      event("graph.launched", 1, { run_id: "r1" }),
      event("graph.node_start", 2, { run_id: "r1", node_id: "a1" }),
      event("swarm.tool_start", 3, { run_id: "r1", node_id: "a1", invocation_id: "i1", tool: "kb_search" }),
      event("swarm.tool_end", 4, { run_id: "r1", node_id: "a1", invocation_id: "other", tool: "kb_search" }),
    ];
    expect(reduceRunActivity(rows)).toEqual({ runs: true, agents: true, invocations: true });
    rows.push(event("swarm.tool_end", 5, { run_id: "r1", node_id: "a1", invocation_id: "i1", tool: "kb_search" }));
    expect(reduceRunActivity(rows).invocations).toBe(false);
  });
});
