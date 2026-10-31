import type { TimelineEntry } from "@/lib/types";

export interface RunActivity {
  runs: boolean;
  agents: boolean;
  invocations: boolean;
}

const RUN_START = new Set([
  "workflow.run_started", "graph.launched", "swarm.launched", "rl.started",
]);
const RUN_END = new Set([
  "workflow.run_succeeded", "workflow.run_failed", "workflow.run_cancelled",
  "graph.completed", "graph.failed", "swarm.completed", "swarm.failed",
  "rl.completed", "rl.failed",
]);
const AGENT_START = new Set([
  "agent.session.start", "graph.node_start", "swarm.node_start",
]);
const AGENT_END = new Set([
  "agent.session.end", "graph.node_stop", "graph.node_error", "swarm.node_stop",
]);
const INVOCATION_START = new Set([
  "invocation.started", "tool.started", "swarm.tool_start",
]);
const INVOCATION_END = new Set([
  "invocation.completed", "invocation.failed", "tool.completed", "tool.failed",
  "swarm.tool_end",
]);

function text(meta: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = meta[key];
    if (typeof value === "string" && value) return value;
  }
  return "";
}

function keys(entry: TimelineEntry) {
  const meta = entry.swarmMeta ?? {};
  const run = entry.workflow_run_id || text(meta, "workflow_run_id", "run_id", "swarm_id", "graph_id") || "unattributed-run";
  const agent = text(meta, "agent_id", "node_id", "session_id") || entry.agent_id || entry.session_id || "unattributed-agent";
  const invocation = text(meta, "invocation_id", "tool_call_id", "tool_use_id");
  const tool = text(meta, "tool", "tool_name") || entry.title;
  return {
    run,
    agent: `${run}:${agent}`,
    invocation: `${run}:${agent}:${invocation || tool}`,
  };
}

function deletePrefixed(keys: Set<string>, prefix: string) {
  for (const key of keys) if (key.startsWith(prefix)) keys.delete(key);
}

/** Reconcile lifecycle starts and terminals in timestamp order. */
export function reduceRunActivity(entries: readonly TimelineEntry[]): RunActivity {
  const runs = new Set<string>();
  const agents = new Set<string>();
  const invocations = new Set<string>();
  const ordered = [...entries].sort((a, b) => a.timestamp - b.timestamp);

  for (const entry of ordered) {
    const event = entry.swarmEventType ?? "";
    const key = keys(entry);
    if (RUN_START.has(event)) runs.add(key.run);
    if (AGENT_START.has(event)) agents.add(key.agent);
    if (INVOCATION_START.has(event)) invocations.add(key.invocation);
    if (INVOCATION_END.has(event)) invocations.delete(key.invocation);
    if (AGENT_END.has(event)) {
      agents.delete(key.agent);
      deletePrefixed(invocations, `${key.agent}:`);
    }
    if (RUN_END.has(event)) {
      runs.delete(key.run);
      deletePrefixed(agents, `${key.run}:`);
      deletePrefixed(invocations, `${key.run}:`);
    }
  }

  return { runs: runs.size > 0, agents: agents.size > 0, invocations: invocations.size > 0 };
}
