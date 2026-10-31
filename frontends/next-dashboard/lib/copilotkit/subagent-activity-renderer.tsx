"use client";

/**
 * Sub-agent activity-message renderers — PARKED (bd:python-factory-esb6n).
 *
 * STATUS: none of these renderers are registered anymore.
 * `ACTIVITY_RENDERERS` in `provider.tsx` contains only terminal.command. The sub-agent
 * containment box (`sub-agent-group.tsx`) is the single surface for every
 * SYNC spawn; the activity cards rendered a SECOND bare card OUTSIDE the
 * box (co-mingling with the coordinator, and with a buggy agent_count=0),
 * which the containment goal forbids. The activity message id
 * `subagent:<tcid>` arrives before the spawn anchor in the stream, so it
 * can't be pulled into the box positionally. meta-architect verdict
 * 298d1bb2 (supersedes 60d5af60).
 *
 * KEPT ON DISK for bd:python-factory-8q8da — which will re-introduce
 * per-node status (pending/running/failed/handoff) INSIDE the box.
 * `NodeSchema` + `NodeRowList` are the reusable pieces; the
 * `swarmActivityRenderer` / `graphActivityRenderer` objects remain
 * exported (and unit-tested) but UNREGISTERED until that work lands.
 *
 * Original wire pin: ``@copilotkitnext/react/dist/hooks/
 *   use-render-activity-message.mjs`` predicate
 *   ``renderer.activityType === message.activityType``; pinned
 *   @copilotkit/[email protected].
 */

import { z } from "zod";
import {
  Workflow, Users, CheckCircle2, Circle, AlertCircle, Loader2,
} from "lucide-react";
import { ToolCallCard } from "./tool-call-card";

// Mirrors the Pydantic NodeActivity contract in
// ``components/ui/src/factory/ui/runtime/ag_ui_activity_models.py``.
const NodeSchema = z.object({
  node_id: z.string(),
  status: z.enum(["pending", "running", "completed", "failed"]),
  started_at: z.number().nullable().optional(),
  stopped_at: z.number().nullable().optional(),
  handoff_from: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
});

const SwarmContent = z.object({
  activityType: z.literal("subagent.swarm"),
  run_id: z.string(),
  swarm_id: z.string(),
  status: z.enum(["running", "completed", "failed"]),
  agent_count: z.number(),
  nodes: z.array(NodeSchema).default([]),
  started_at: z.number(),
  completed_at: z.number().nullable().optional(),
  error: z.string().nullable().optional(),
});

const GraphContent = z.object({
  activityType: z.literal("subagent.graph"),
  run_id: z.string(),
  graph_id: z.string(),
  status: z.enum(["running", "completed", "failed"]),
  nodes: z.array(NodeSchema).default([]),
  started_at: z.number(),
  completed_at: z.number().nullable().optional(),
  error: z.string().nullable().optional(),
});

type NodeRow = z.infer<typeof NodeSchema>;
type SwarmRow = z.infer<typeof SwarmContent>;
type GraphRow = z.infer<typeof GraphContent>;

function statusToCardStatus(
  status: "running" | "completed" | "failed",
): "inProgress" | "executing" | "complete" {
  return status === "running" ? "executing" : "complete";
}

function NodeRowList({ nodes }: { nodes: NodeRow[] }) {
  if (nodes.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic">
        No nodes started yet…
      </div>
    );
  }
  return (
    <div className="space-y-1">
      {nodes.map((row) => (
        <NodeRowItem key={row.node_id} row={row} />
      ))}
    </div>
  );
}

function NodeRowItem({ row }: { row: NodeRow }) {
  const Icon =
    row.status === "completed"
      ? CheckCircle2
      : row.status === "failed"
        ? AlertCircle
        : row.status === "running"
          ? Loader2
          : Circle;
  const iconColor =
    row.status === "completed"
      ? "text-emerald-500"
      : row.status === "failed"
        ? "text-red-500"
        : row.status === "running"
          ? "text-blue-500"
          : "text-muted-foreground";
  const spin = row.status === "running" ? "animate-spin" : "";
  return (
    <div className="flex items-center gap-2 text-[11px] py-0.5">
      <Icon className={`h-3 w-3 shrink-0 ${iconColor} ${spin}`} />
      <span className="font-mono text-foreground/80 truncate">
        {row.node_id}
      </span>
      {row.handoff_from && (
        <span className="text-muted-foreground truncate ml-auto">
          ← {row.handoff_from}
        </span>
      )}
      {row.error && (
        <span className="text-red-500 truncate ml-auto">{row.error}</span>
      )}
    </div>
  );
}

/* subagent.single — REMOVED (bd:python-factory-esb6n).
   The `singleSubagentActivityRenderer` rendered a "Sub-agent · {id}" card
   from the subagent.single activityType, which duplicated the sub-agent
   containment box header (`sub-agent-group.tsx`). The box is now the single
   surface that names a spawn_subagent run, so this renderer was deleted and
   dropped from ACTIVITY_RENDERERS in provider.tsx. The backend still emits
   the subagent.single activity (open/close); with no matching renderer the
   CopilotKit dispatcher falls through to null — invisible, harmless. swarm
   + graph activity renderers below are unaffected. */

export const swarmActivityRenderer = {
  activityType: "subagent.swarm" as const,
  content: SwarmContent,
  render: ({ content }: { content: SwarmRow }) => {
    const title = `Swarm · ${content.agent_count} agents`;
    return (
      <ToolCallCard
        name="agent_launch_swarm"
        title={title}
        status={statusToCardStatus(content.status)}
        icon={<Users className="h-3.5 w-3.5" />}
      >
        <NodeRowList nodes={content.nodes} />
      </ToolCallCard>
    );
  },
};

export const graphActivityRenderer = {
  activityType: "subagent.graph" as const,
  content: GraphContent,
  render: ({ content }: { content: GraphRow }) => {
    const title = `Workflow · ${content.graph_id}`;
    return (
      <ToolCallCard
        name="agent_invoke_graph"
        title={title}
        status={statusToCardStatus(content.status)}
        icon={<Workflow className="h-3.5 w-3.5" />}
      >
        <NodeRowList nodes={content.nodes} />
      </ToolCallCard>
    );
  },
};

/**
 * No-op export — actual activity renderer registration happens via
 * ``renderActivityMessages`` prop in ``provider.tsx`` (bd-6zyg).
 * The no-arg useRenderActivityMessage() call was removed (bd:jsofg)
 * because it triggered 'must be a stable array' console spam.
 */
export function useSubagentActivityHook() {
  // intentionally empty — registration is prop-based, not hook-based
}
