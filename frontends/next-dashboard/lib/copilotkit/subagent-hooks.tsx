"use client";

/**
 * Sub-agent watch-live renderers (bd-71a0).
 *
 * Claims `agent_invoke_graph` and `agent_launch_swarm` MCP tool
 * names so a chat turn that dispatches a sub-graph or swarm renders as
 * an inline ToolCallCard with live child rows fed by useLiveToolStream.
 *
 * Backend correlation (bd-71a0 patch): the per-node events
 * (swarm.node_start/handoff/node_stop, graph.node_start/node_error/
 * node_stop) now carry run_id. live-tool-events.ts:88 coalesces
 * payload.workflow_run_id || payload.run_id into TimelineEntry.workflow_run_id.
 * <SubagentChildRows> filters the live stream by exact run_id match.
 *
 * Wire tool names verified via /api/tools live + lazy_loader prefix logic:
 *   - agent_invoke_graph: invoke_graph + 'agent_' prefix → agent_invoke_graph
 *   - agent_launch_swarm: agent_launch_swarm starts with 'agent_' so
 *     bases/mcp_server/runtime/lazy_loader.py:179 does NOT add another
 *     prefix → agent_launch_swarm (single prefix). Confirmed by GET
 *     http://localhost:8000/api/tools.
 *
 * Dispatcher source pin: @copilotkitnext/[email protected]
 *   - dist/hooks/use-render-tool.mjs registers by exact name into
 *     copilotkit.renderToolCalls (last-write-wins, no warning)
 *   - dist/hooks/use-render-tool-call.mjs:55-57 — strict triple-equals
 *     `rc.name === toolCall.function.name`; wildcard `"*"` is the last
 *     fallback in a four-step chain (agentId-bound exact → unbound exact
 *     → first exact → wildcard).
 * @copilotkit/[email protected] is a re-export of @copilotkitnext/react.
 */

import { useRenderTool } from "@copilotkit/react-core/v2";
import { z } from "zod";
import {
  Workflow,
  Users,
  CheckCircle2,
  Circle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { ToolCallCard, parseResult } from "./tool-call-card";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";
import type { TimelineEntry } from "@/lib/types";

const InvokeGraphArgs = z.object({
  graph_id: z.string().optional(),
  task: z.string().optional(),
  context: z.unknown().optional(),
});

const LaunchSwarmArgs = z.object({
  prompt: z.string().optional(),
  agents: z.array(z.unknown()).optional(),
});

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

function extractRunId(parameters: unknown, parsed: unknown): string | undefined {
  const params = parameters as
    | { context?: { workflow_run_id?: string; run_id?: string }; run_id?: string }
    | undefined;
  const result = parsed as { run_id?: string; workflow_run_id?: string } | undefined;
  return (
    result?.run_id ??
    result?.workflow_run_id ??
    params?.context?.workflow_run_id ??
    params?.context?.run_id ??
    params?.run_id ??
    undefined
  );
}

export function useInvokeGraphRenderer() {
  useRenderTool({
    name: "agent_invoke_graph",
    parameters: InvokeGraphArgs,
    render: ({ status, parameters, result }) => {
      const parsed = parseResult(result);
      const runId = extractRunId(parameters, parsed);
      const title = parameters?.graph_id
        ? `Workflow · ${truncate(parameters.graph_id, 40)}`
        : "Workflow";
      return (
        <ToolCallCard
          name="agent_invoke_graph"
          title={title}
          status={status}
          icon={<Workflow className="h-3.5 w-3.5" />}
        >
          <SubagentChildRows runId={runId} />
        </ToolCallCard>
      );
    },
  });
}

export function useLaunchSwarmRenderer() {
  useRenderTool({
    name: "agent_launch_swarm",
    parameters: LaunchSwarmArgs,
    render: ({ status, parameters, result }) => {
      const parsed = parseResult(result);
      const runId = extractRunId(parameters, parsed);
      const agentCount = Array.isArray(parameters?.agents)
        ? parameters.agents.length
        : 0;
      const title = agentCount > 0 ? `Swarm · ${agentCount} agents` : "Swarm";
      return (
        <ToolCallCard
          name="agent_launch_swarm"
          title={title}
          status={status}
          icon={<Users className="h-3.5 w-3.5" />}
        >
          <SubagentChildRows runId={runId} />
        </ToolCallCard>
      );
    },
  });
}

function SubagentChildRows({ runId }: { runId: string | undefined }) {
  const { entries } = useLiveToolStream();
  if (!runId) {
    return (
      <div className="text-xs text-muted-foreground italic">
        Waiting for run id…
      </div>
    );
  }
  const childRows = entries
    .filter((e) => e.type === "swarm_event" && e.workflow_run_id === runId)
    .slice(0, 50)
    .reverse();
  if (childRows.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic">
        No nodes started yet…
      </div>
    );
  }
  return (
    <div className="space-y-1">
      {childRows.map((row) => (
        <SubagentChildRow key={row.id} entry={row} />
      ))}
    </div>
  );
}

function SubagentChildRow({ entry }: { entry: TimelineEntry }) {
  const Icon =
    entry.status === "completed"
      ? CheckCircle2
      : entry.status === "failed"
        ? AlertCircle
        : entry.status === "running"
          ? Loader2
          : Circle;
  const iconColor =
    entry.status === "completed"
      ? "text-emerald-500"
      : entry.status === "failed"
        ? "text-red-500"
        : entry.status === "running"
          ? "text-blue-500"
          : "text-muted-foreground";
  const spin = entry.status === "running" ? "animate-spin" : "";
  return (
    <div className="flex items-center gap-2 text-[11px] py-0.5">
      <Icon className={`h-3 w-3 shrink-0 ${iconColor} ${spin}`} />
      <span className="font-mono text-foreground/80 truncate">
        {entry.title}
      </span>
      {entry.detail && (
        <span className="text-muted-foreground truncate ml-auto">
          {entry.detail}
        </span>
      )}
    </div>
  );
}
