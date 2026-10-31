"use client";

import React, { createContext, useContext } from "react";

/**
 * Transcript sink seam (bd:3jcls.7).
 *
 * A human-fired action must land in the SAME transcript as an agent-fired
 * one — otherwise the human path and the agent path become two products that
 * disagree, and the agent gives stale advice because it never learned what
 * the human just did.
 *
 * The shared renderer stays framework-agnostic (tenet 2), so it does not
 * import CopilotKit or `@ag-ui/client`. It emits a neutral
 * {@link TranscriptEntry} through this optional sink; the host converts it
 * into SDK message objects. The Next dashboard's implementation uses the
 * installed `@ag-ui/client` `AbstractAgent.addMessages` (index.d.ts:434-436)
 * via `useAgent` from `@copilotkitnext/react` — no bespoke event machinery,
 * and no `ACTIVITY_*` events (those are for sub-agent watch-live cards).
 *
 * With no provider mounted the sink is absent and dispatch still works; the
 * transcript mirror is additive, never load-bearing for the call itself.
 */

export interface TranscriptEntry {
  /** Stable id for the synthetic tool call — links the two messages. */
  toolCallId: string;
  /** Resolved MCP tool name, exactly as the agent path would report it. */
  toolName: string;
  /** Resolved arguments. */
  args: Record<string, unknown>;
  /** Tool result payload, or the error when `ok` is false. */
  result: unknown;
  /** Whether the dispatch succeeded. */
  ok: boolean;
}

export type TranscriptSink = (entry: TranscriptEntry) => void;

const TranscriptContext = createContext<TranscriptSink | null>(null);

export function TranscriptSinkProvider({
  sink,
  children,
}: {
  sink: TranscriptSink;
  children: React.ReactNode;
}) {
  return <TranscriptContext.Provider value={sink}>{children}</TranscriptContext.Provider>;
}

/** Read the host-supplied sink, or `null` when none is mounted. */
export function useTranscriptSink(): TranscriptSink | null {
  return useContext(TranscriptContext);
}
