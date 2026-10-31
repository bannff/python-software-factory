import type { TimelineEntry } from "@/lib/types";
export interface ToolEvent {
  brick: string;
  tool: string;
  success: boolean;
  latency_ms: number;
  ts: number;
  session_id?: string;
  workflow_run_id?: string;
  args_summary?: Record<string, unknown>;
  caller?: string;
  result_summary?: Record<string, unknown>;
  phase?: "start" | "result" | "error";
  invocation_id?: string;
  correlation_id?: string;
  parent_invocation_id?: string;
}

/** Events bridged from the events brick (swarm lifecycle, game, etc.) */
export interface ActivityEvent {
  event_type: string;
  source: string;
  payload: Record<string, unknown>;
  ts: number;
}

export type SSEEvent = ToolEvent | ActivityEvent;

function isActivityEvent(evt: SSEEvent): evt is ActivityEvent {
  return "event_type" in evt;
}

const SWARM_STATUS: Record<string, TimelineEntry["status"]> = {
  "agent.session.start": "completed",
  "agent.session.end": "completed",
  "swarm.launched": "running",
  "swarm.node_start": "running",
  "swarm.handoff": "running",
  "swarm.node_stop": "completed",
  "swarm.completed": "completed",
  "swarm.failed": "failed",
  "swarm.tool_start": "running",
  "swarm.tool_end": "completed",
  "swarm.agent_handoff": "running",
  "graph.launched": "running",
  "graph.node_start": "running",
  "graph.node_stop": "completed",
  "graph.node_error": "failed",
  "graph.completed": "completed",
  "graph.failed": "failed",
  "workflow.run_started": "running",
  "workflow.attempt_started": "running",
  "workflow.attempt_stream_event": "running",
  "workflow.attempt_completed": "completed",
  "workflow.step_transition": "completed",
  "workflow.run_succeeded": "completed",
  "workflow.run_failed": "failed",
  "workflow.run_cancelled": "completed",
  "rl.started": "running",
  "rl.findings.collected": "completed",
  "rl.scored": "completed",
  "rl.reward.processed": "completed",
  "rl.memory.processed": "completed",
  "rl.completed": "completed",
  "rl.failed": "failed",
};

const SWARM_LABEL: Record<string, string> = {
  "agent.session.start": "Agent run started",
  "agent.session.end": "Agent run ended",
  "swarm.launched": "Swarm launched",
  "swarm.node_start": "Agent started",
  "swarm.handoff": "Handoff",
  "swarm.node_stop": "Agent stopped",
  "swarm.completed": "Swarm completed",
  "swarm.failed": "Swarm failed",
  "swarm.tool_start": "Tool call",
  "swarm.tool_end": "Tool done",
  "swarm.agent_handoff": "Agent handoff",
  "graph.launched": "Graph run started",
  "graph.node_start": "Agent started",
  "graph.node_stop": "Agent stopped",
  "graph.node_error": "Agent failed",
  "graph.completed": "Graph run completed",
  "graph.failed": "Graph run failed",
  "workflow.run_started": "Workflow run started",
  "workflow.attempt_started": "Workflow attempt started",
  "workflow.attempt_stream_event": "Workflow attempt stream",
  "workflow.attempt_completed": "Workflow attempt completed",
  "workflow.step_transition": "Workflow step transition",
  "workflow.run_succeeded": "Workflow run succeeded",
  "workflow.run_failed": "Workflow run failed",
  "workflow.run_cancelled": "Workflow run cancelled",
  "rl.started": "RL started",
  "rl.findings.collected": "RL findings collected",
  "rl.scored": "RL scored",
  "rl.reward.processed": "RL reward processed",
  "rl.memory.processed": "RL memory processed",
  "rl.completed": "RL completed",
  "rl.failed": "RL failed",
};

function formatRlDetail(etype: string, payload: Record<string, unknown>): string | undefined {
  if (etype === "rl.scored") {
    const f1 = payload.f1;
    return typeof f1 === "number" ? `F1 ${f1.toFixed(2)}` : undefined;
  }
  if (etype === "rl.findings.collected") {
    const findings = payload.findings_count;
    const gt = payload.gt_entries_count;
    if (typeof findings === "number" && typeof gt === "number") {
      return `${findings} findings vs ${gt} GT`;
    }
  }
  if (etype === "rl.reward.processed") {
    const outcome = typeof payload.outcome === "string" ? payload.outcome : "processed";
    const amount = payload.amount;
    if (typeof amount === "number" && amount > 0) {
      return `${outcome} · ${amount}`;
    }
    return outcome;
  }
  if (etype === "rl.memory.processed") {
    return typeof payload.outcome === "string" ? payload.outcome : undefined;
  }
  return undefined;
}

function activityStatus(etype: string, payload: Record<string, unknown>): TimelineEntry["status"] {
  if (etype === "workflow.attempt_completed" || etype === "workflow.step_transition") {
    const status = payload.status;
    if (status === "failed") return "failed";
    if (["pending", "running", "waiting"].includes(String(status))) return "running";
    return "completed";
  }
  return SWARM_STATUS[etype] || "running";
}

export function mapLiveActivityEvent(evt: ActivityEvent, id: string): TimelineEntry {
  const etype = evt.event_type;
  const payload = evt.payload || {};
  const agentId = (payload.agent_id as string) || (payload.node_id as string) || "";
  const toolName = (payload.tool as string) || "";
  const swarmId = (payload.swarm_id as string) || "";
  const baseLabel = SWARM_LABEL[etype] || etype;
  const workflow_run_id = (payload.workflow_run_id as string) || (payload.run_id as string) || undefined;
  const session_id = (payload.session_id as string) || undefined;
  const nativeEventType = etype === "workflow.attempt_stream_event"
    && typeof payload.native_event_type === "string" ? payload.native_event_type : "";
  const detail = formatRlDetail(etype, payload)
    || (nativeEventType ? `${nativeEventType}${agentId ? ` · ${agentId}` : ""}` : "")
    || swarmId || agentId || evt.source;

  let title = baseLabel;
  if (etype === "workflow.attempt_stream_event" && nativeEventType) {
    title = `${baseLabel} · ${nativeEventType}`;
  } else if (etype === "swarm.tool_start" || etype === "swarm.tool_end") {
    title = `${baseLabel} · ${toolName}`;
    if (agentId) title = `[${agentId}] ${title}`;
  } else if (etype === "swarm.agent_handoff") {
    const from = (payload.from_agent as string) || "";
    const to = (payload.to_agent as string) || "";
    title = `${baseLabel} · ${from} → ${to}`;
  } else if (agentId) {
    title = `${baseLabel} · ${agentId}`;
  }

  return {
    id,
    type: "swarm_event",
    title,
    status: activityStatus(etype, payload),
    timestamp: evt.ts * 1000,
    duration: (payload.duration_ms as number) || undefined,
    detail,
    workflow_run_id,
    session_id,
    swarmEventType: etype,
    swarmMeta: payload,
  };
}

export function mapLiveToolEvent(evt: ToolEvent, id: string): TimelineEntry {
  return {
    id,
    type: "tool_call",
    title: evt.tool,
    status: evt.phase === "start" ? "running" : evt.success ? "completed" : "failed",
    timestamp: evt.ts * 1000,
    duration: evt.latency_ms,
    detail: evt.brick,
    workflow_run_id: evt.workflow_run_id,
    session_id: evt.session_id,
    args_summary: evt.args_summary,
    caller: evt.caller,
    result_summary: evt.result_summary,
  };
}

export function mapLiveStreamEvent(evt: SSEEvent, id: string): TimelineEntry {
  return isActivityEvent(evt)
    ? mapLiveActivityEvent(evt, id)
    : mapLiveToolEvent(evt, id);
}