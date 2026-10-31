"use client";

/**
 * Sub-agent detection helpers (bd:python-factory-ywurg, esb6n).
 *
 * Pure detection logic shared by the sub-agent containment box
 * (`sub-agent-grouping.ts`) and the wildcard pill suppressor
 * (`tool-renderers.tsx::isSubAgentToolCall`):
 *   - `SPAWN_TOOL_NAMES` — all five spawn_* tool names.
 *   - `SYNC_SPAWN_TOOL_NAMES` — the four SYNC spawns that form a
 *     containment box (excludes `spawn_subagent_async`, which is the
 *     separate BackgroundSpawnWindow live-window surface).
 *   - `spawnAgentLabel` — raw agent id from a spawn tool call's args.
 *   - `spawnBoxLabel` — the box HEADER label (tool-name aware:
 *     "Swarm · N agents" / "Pipeline · …" / "Sub-agent · id").
 *
 * History: this module used to also render a dim "agent-id" attribution
 * chip above sub-agent text bubbles (`withSubAgentAttribution`) and a
 * positional `resolveSubAgentId` backward-walk. Both were retired under
 * bd:python-factory-esb6n — the containment box's header now names the
 * agent (chip duplicate), and the box groups by positional contiguous run
 * anchored on the spawn tool-call id (so the backward-walk is unused).
 */

import type { Message } from "@ag-ui/core";

export const SPAWN_TOOL_NAMES = new Set([
  "spawn_subagent",
  "spawn_swarm",
  "spawn_graph",
  "spawn_registered_graph",
  "spawn_subagent_async",
]);

/**
 * The SYNC spawns that form an in-band containment box. `spawn_subagent_async`
 * is excluded — it renders a live BackgroundSpawnWindow keyed off its own
 * run_id SSE, a separate surface that should not be boxed (bd:python-factory-esb6n).
 */
export const SYNC_SPAWN_TOOL_NAMES = new Set([
  "spawn_subagent",
  "spawn_swarm",
  "spawn_graph",
  "spawn_registered_graph",
]);

/** A minimal tool-call shape — just what we read for the agent label. */
interface SpawnToolCall {
  function: { name: string; arguments?: string };
}

function parseSpawnArgs(spawnCall: SpawnToolCall): Record<string, unknown> {
  try {
    return JSON.parse(spawnCall.function.arguments ?? "{}") as Record<
      string,
      unknown
    >;
  } catch {
    return {};
  }
}

/**
 * Extract the raw agent id from a spawn_* tool call's args. Falls back to
 * the tool name minus the `spawn_` prefix. (Used where the bare agent id
 * is wanted; the box HEADER uses `spawnBoxLabel` instead.)
 */
export function spawnAgentLabel(spawnCall: SpawnToolCall): string {
  const args = parseSpawnArgs(spawnCall);
  return (
    (args.agent_id as string | undefined) ??
    (args.agent_ids as string[] | undefined)?.[0] ??
    (args.graph_id as string | undefined) ??
    spawnCall.function.name.replace("spawn_", "")
  );
}

/**
 * The containment-box HEADER label for a spawn tool call. Tool-name aware
 * so a swarm reads "Swarm · 2 agents" (not the misleading first agent id),
 * a graph reads "Pipeline · N nodes", a registered graph reads
 * "Pipeline · {graph_id}", and a single spawn reads "Sub-agent · {id}"
 * (byte-identical to the pre-extension header). The box header inherits
 * the title semantics that the spawn renderers shed when they dropped
 * their ToolCallCard chrome (bd:python-factory-esb6n).
 */
export function spawnBoxLabel(spawnCall: SpawnToolCall): string {
  const name = spawnCall.function.name;
  const args = parseSpawnArgs(spawnCall);
  if (name === "spawn_swarm") {
    const n = (args.agent_ids as string[] | undefined)?.length ?? 0;
    return `Swarm · ${n} agents`;
  }
  if (name === "spawn_graph") {
    const n = (args.agent_ids as string[] | undefined)?.length ?? 0;
    return `Pipeline · ${n} nodes`;
  }
  if (name === "spawn_registered_graph") {
    return `Pipeline · ${(args.graph_id as string | undefined) ?? "…"}`;
  }
  // spawn_subagent (and any future single-agent spawn)
  return `Sub-agent · ${(args.agent_id as string | undefined) ?? "…"}`;
}

// Re-export Message so consumers importing it from here keep working.
export type { Message };
