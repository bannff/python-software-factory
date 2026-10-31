"use client";

/**
 * Live canvas-state subscription for CopilotKit v2 (bd:python-factory-ewde,
 * child of epic python-factory-iet5 "Agent Driven UI", bd-E).
 *
 * Replaces the v1→v2 cutover stub (returned empty defaults) with a real
 * subscription to the Companion-X agent's state. Producer side: bd-D
 * (`python-factory-syh1`) ships ``ui_paint_canvas`` as the carrier #2 MCP
 * tool, ``StateDeltaPlugin`` translates the result-tagged sentinel into
 * ``StateDeltaEvent``, and the AG-UI mapper emits ``STATE_SNAPSHOT`` then
 * ``STATE_DELTA`` (RFC 6902 ``replace`` ops on ``/canvas/<slot>``) over the
 * chat stream. Consumer side: CopilotKit v2's ``StateManager`` applies the
 * patches and surfaces the result on ``agent.state.canvas.<slot>`` (see
 * ``@ag-ui/[email protected]/dist/index.mjs`` ``defaultApplyEvents`` and
 * ``@copilotkitnext/[email protected]/dist/index.mjs:1226`` ``handleStateSnapshot``).
 *
 * Subscription primitive: ``useAgent({agentId, updates: [OnStateChanged]})``
 * from ``@copilotkitnext/react`` (re-exported from
 * ``@copilotkitnext/[email protected]``). On every state mutation the hook
 * ``forceUpdate``s the calling component; there is no per-key selector
 * (verified against
 * ``node_modules/@copilotkitnext/react/dist/hooks/use-agent.mjs:67-83``).
 * Per-slot memoisation is the canvas-view's job (bd-F), not this hook's.
 *
 * State shape per ``.agents/steering/a2ui-protocol.md`` (carrier #2):
 * ``state.canvas.{graph|timeline|findings|canvas}`` each holds an A2UI
 * payload ``{components: [...], name?: string}``. Legacy ``_a2ui_*``
 * top-level fields are dropped.
 *
 * Identity + scoping: ``COMPANION_X_AGENT_ID = "companion_x"`` is a single
 * shared identity. ``StateManager`` keys state by ``(agentId, threadId,
 * runId)`` so multi-tab opens N threads = N independent canvas states.
 *
 * Return prop shape preserves the v1 contract — ``steps``, ``toolCalls``,
 * ``agentState``, ``isLoading`` — so canvas views (graph-view, timeline-
 * view-v2, findings-view, welcome-view) keep their existing prop signatures.
 * Re-keying consumer reads from ``agentState._a2ui_<slot>`` to
 * ``agentState.canvas?.<slot>?`` is bd-F's scope.
 */

import { useAgent, UseAgentUpdate } from "@copilotkit/react-core/v2";

import { COMPANION_X_AGENT_ID } from "@/lib/copilotkit/companion-agent";
import type { CanvasState } from "@/lib/copilotkit/a2ui-canvas-slots";
import type { ActiveToolCall, Step } from "@/lib/types";

export type { CanvasSlot, CanvasState } from "@/lib/copilotkit/a2ui-canvas-slots";

interface CopilotCanvasState {
  steps: Step[];
  toolCalls: ActiveToolCall[];
  agentState: { canvas?: CanvasState } & Record<string, unknown>;
  isLoading: boolean;
}

const EMPTY_STEPS: Step[] = [];
const EMPTY_TOOL_CALLS: ActiveToolCall[] = [];

export function useCopilotCanvasState(): CopilotCanvasState {
  const { agent } = useAgent({
    agentId: COMPANION_X_AGENT_ID,
    updates: [UseAgentUpdate.OnStateChanged],
  });

  const agentState =
    ((agent?.state ?? {}) as { canvas?: CanvasState } & Record<string, unknown>);
  const isLoading = !agent;

  return {
    steps: EMPTY_STEPS,
    toolCalls: EMPTY_TOOL_CALLS,
    agentState,
    isLoading,
  };
}
