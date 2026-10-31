"use client";

/**
 * Spawn-tool named renderers (bd:python-factory-b6z01, r3eqj).
 *
 * Claims five spawn tools (sync + async) so every spawn call gets a
 * labelled ToolCallCard instead of the generic wildcard pill.
 *
 * These tools are native Strands @tool functions riding `tool_stream`
 * directly. Wire names verified via GET /api/tools on the running stack.
 *
 * Dispatcher source pin: @copilotkitnext/[email protected]
 *   dist/hooks/use-render-tool.mjs — registers by exact name, last-write-wins.
 *   dist/hooks/use-render-tool-call.mjs:55-57 — strict triple-equals name match.
 *   @copilotkit/[email protected] re-exports @copilotkitnext/react.
 *
 * bd:python-factory-0zkj4 — spawn_subagent renders nested sub-agent tool
 * calls via SubAgentToolRows (only during "executing"/"complete").
 * bd:python-factory-r3eqj — spawn_subagent_async renders BackgroundSpawnWindow
 * subscribed to /api/stream/run/{run_id} SSE (P2a).
 */

import { useRenderTool, useAgent, UseAgentUpdate } from "@copilotkit/react-core/v2";
import type { Message } from "@ag-ui/core";
import { z } from "zod";
import { Bot } from "lucide-react";
import { ToolCallCard, parseResult } from "./tool-call-card";
import { SubAgentToolRows } from "./spawn-tool-rows";
import { BackgroundSpawnWindow } from "./background-spawn-window";
import { COMPANION_X_AGENT_ID } from "./companion-agent";

/** Find the most recent toolCallId for a given spawn tool name in agent.messages. */
function findSpawnToolCallId(messages: Message[], toolName: string): string | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.role !== "assistant") continue;
    const tc = (msg as Extract<Message, { role: "assistant" }>).toolCalls?.find(
      (t) => t.function.name === toolName,
    );
    if (tc) return tc.id;
  }
  return undefined;
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/* spawn_subagent ---------------------------------------------------- */

const SpawnSubagentArgs = z.object({
  agent_id: z.string().optional(),
  task: z.string().optional(),
});

export function useSpawnSubagentRenderer() {
  const { agent } = useAgent({
    agentId: COMPANION_X_AGENT_ID,
    updates: [UseAgentUpdate.OnMessagesChanged],
  });

  useRenderTool({
    name: "spawn_subagent",
    parameters: SpawnSubagentArgs,
    // CHROME-LESS by design (bd:python-factory-esb6n, meta-architect
    // verdict 69cf6476 option b): the sub-agent containment box
    // (`sub-agent-group.tsx`) is the ONE container — it owns the single
    // header ("Sub-agent · {id}"), border, and collapse. This renderer
    // contributes ONLY the nested tool-call pills, so wrapping it in a
    // ToolCallCard here would double the header + border (the bug this
    // bead fixes). The pills keep their icons + spinner/check status.
    render: ({ status, parameters }) => {
      const spawnToolCallId = findSpawnToolCallId(agent.messages, "spawn_subagent");
      const showRows = status !== "inProgress";
      if (!showRows) {
        // Args still streaming — the box header already shows the agent
        // id + Running pill, so emit nothing until rows are ready.
        return <></>;
      }
      return <SubAgentToolRows spawnToolCallId={spawnToolCallId} />;
    },
  });
}

/* spawn_swarm ------------------------------------------------------- */

const SpawnSwarmArgs = z.object({
  agent_ids: z.array(z.string()).optional(),
  task: z.string().optional(),
});

export function useSpawnSwarmRenderer() {
  const { agent } = useAgent({
    agentId: COMPANION_X_AGENT_ID,
    updates: [UseAgentUpdate.OnMessagesChanged],
  });

  useRenderTool({
    name: "spawn_swarm",
    parameters: SpawnSwarmArgs,
    // CHROME-LESS (bd:python-factory-esb6n): the containment box owns the
    // single header ("Swarm · N agents") + border. This renderer emits
    // only the nested tool-call pills.
    render: ({ status }) => {
      const spawnToolCallId = findSpawnToolCallId(agent.messages, "spawn_swarm");
      if (status === "inProgress") return <></>;
      return <SubAgentToolRows spawnToolName="spawn_swarm" spawnToolCallId={spawnToolCallId} />;
    },
  });
}

/* spawn_graph ------------------------------------------------------- */

const SpawnGraphArgs = z.object({
  agent_ids: z.array(z.string()).optional(),
  edges: z.array(z.unknown()).optional(),
  task: z.string().optional(),
});

export function useSpawnGraphRenderer() {
  const { agent } = useAgent({
    agentId: COMPANION_X_AGENT_ID,
    updates: [UseAgentUpdate.OnMessagesChanged],
  });

  useRenderTool({
    name: "spawn_graph",
    parameters: SpawnGraphArgs,
    // CHROME-LESS (bd:python-factory-esb6n): box owns the "Pipeline · N
    // nodes" header; this renderer emits only the nested pills.
    render: ({ status }) => {
      const spawnToolCallId = findSpawnToolCallId(agent.messages, "spawn_graph");
      if (status === "inProgress") return <></>;
      return <SubAgentToolRows spawnToolName="spawn_graph" spawnToolCallId={spawnToolCallId} />;
    },
  });
}

/* spawn_registered_graph ------------------------------------------- */

const SpawnRegisteredGraphArgs = z.object({
  graph_id: z.string().optional(),
  task: z.string().optional(),
});

export function useSpawnRegisteredGraphRenderer() {
  const { agent } = useAgent({
    agentId: COMPANION_X_AGENT_ID,
    updates: [UseAgentUpdate.OnMessagesChanged],
  });

  useRenderTool({
    name: "spawn_registered_graph",
    parameters: SpawnRegisteredGraphArgs,
    // CHROME-LESS (bd:python-factory-esb6n): box owns the "Pipeline ·
    // {graph_id}" header; this renderer emits only the nested pills.
    render: ({ status }) => {
      const spawnToolCallId = findSpawnToolCallId(agent.messages, "spawn_registered_graph");
      if (status === "inProgress") return <></>;
      return <SubAgentToolRows spawnToolName="spawn_registered_graph" spawnToolCallId={spawnToolCallId} />;
    },
  });
}

/* spawn_subagent_async ---------------------------------------------- */

const SpawnSubagentAsyncArgs = z.object({
  agent_id: z.string().optional(),
  task: z.string().optional(),
});

export function useSpawnSubagentAsyncRenderer() {
  useRenderTool({
    name: "spawn_subagent_async",
    parameters: SpawnSubagentAsyncArgs,
    render: ({ status, parameters, result }) => {
      const parsed = parseResult(result) as Record<string, unknown> | undefined;
      const runId = (parsed?.run_id as string | undefined) ?? null;
      const agentId = parameters?.agent_id ?? (parsed?.agent_id as string | undefined) ?? "…";
      const title = `Sub-agent · ${agentId} (async)`;
      const preview = parameters?.task ? truncate(parameters.task, 60) : undefined;
      return (
        <ToolCallCard
          name="spawn_subagent_async"
          title={title}
          status={status}
          icon={<Bot className="h-3.5 w-3.5 text-blue-400" />}
          previewLine={preview}
        >
          {runId && <BackgroundSpawnWindow runId={runId} agentId={agentId} />}
        </ToolCallCard>
      );
    },
  });
}
