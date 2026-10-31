"use client";

import { useCallback, useMemo } from "react";
import { useAgent } from "@copilotkit/react-core/v2";
import {
  InvalidationProvider,
  TranscriptSinkProvider,
  type TranscriptEntry,
} from "@companion-x/shared-renderer";
import { COMPANION_X_AGENT_ID } from "./companion-agent";

/**
 * One transcript for humans and agents (bd:python-factory-3jcls.7).
 *
 * A human-fired view action is mirrored into the agent's message list as the
 * SAME two messages the agent path produces: an assistant message carrying
 * the `toolCall`, then a `role: "tool"` result keyed by the same
 * `toolCallId`. Structurally identical, so the existing tool-card renderers
 * paint it with no special case, and the scrollback interleaves human and
 * agent work.
 *
 * That is the point rather than a side effect: those messages ride the next
 * `POST /ag-ui/run` body, so the agent SEES what the human just did instead
 * of giving stale advice and duplicating the work.
 *
 * SDK-first, verified against the installed packages:
 *   - `@ag-ui/[email protected]` `AbstractAgent.addMessages(messages)` —
 *     `node_modules/@ag-ui/client/dist/index.d.ts:435`.
 *   - Message shapes from `@ag-ui/core` `AssistantMessageSchema` (:201) and
 *     `ToolMessageSchema` (:360).
 *   - Handle from `useAgent` — `@copilotkitnext/react`
 *     `dist/hooks/use-agent.d.mts`.
 *
 * Deliberately NOT `ACTIVITY_*` events: those are the sub-agent watch-live
 * card channel (`lib/copilotkit/provider.tsx` `ACTIVITY_RENDERERS`), not the
 * tool-call transcript.
 *
 * KNOWN LIMIT — the mirror is client-side only, so it lives as long as the
 * chat stays mounted. `CopilotChat` calls `copilotkit.connectAgent` on mount,
 * which does `agent.setMessages([])`
 * (`@copilotkitnext/core/dist/index.mjs:799`), so a reload or a chat remount
 * drops it. That is fine for the real interaction (rail and canvas are
 * co-mounted, verified in the browser: the human `cache_get` call rode the
 * next run body as `["assistant:cache_get","tool","user"]`). Durable
 * cross-reload history would need the dispatcher to append to the server-side
 * chat session — a separate change. Backend provenance is already durable:
 * `ui_dispatch_action` stamps `caller_hint = "human:<principal>"` on the
 * envelope, so graph_sink / the timeline record it regardless.
 */
export function ActionTranscriptProvider({ children }: { children: React.ReactNode }) {
  // `updates: []` — we only WRITE to the agent. Subscribing to message
  // changes here would force a re-render of the whole app subtree on every
  // streamed token, since this provider wraps `{children}`.
  const { agent } = useAgent({ agentId: COMPANION_X_AGENT_ID, updates: [] });

  const sink = useCallback(
    (entry: TranscriptEntry) => {
      if (!agent) return;
      const content = safeJson(entry.result);
      agent.addMessages([
        {
          id: `human-action-${entry.toolCallId}`,
          role: "assistant",
          toolCalls: [
            {
              id: entry.toolCallId,
              type: "function",
              function: { name: entry.toolName, arguments: safeJson(entry.args) },
            },
          ],
        },
        {
          id: `human-action-result-${entry.toolCallId}`,
          role: "tool",
          toolCallId: entry.toolCallId,
          content,
          ...(entry.ok ? {} : { error: content }),
        },
      ]);
    },
    [agent],
  );

  // InvalidationProvider lives here too: both are the host wiring that turns
  // a dispatch into a visible consequence (transcript entry + data refresh).
  return useMemo(
    () => (
      <TranscriptSinkProvider sink={sink}>
        <InvalidationProvider>{children}</InvalidationProvider>
      </TranscriptSinkProvider>
    ),
    [sink, children],
  );
}

/** `arguments` and tool `content` are strings on the wire, never objects. */
function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value ?? null);
  } catch {
    return String(value);
  }
}
