/**
 * Sub-agent containment grouping — pure logic (bd:python-factory-esb6n).
 *
 * Partitions the flat CopilotKit message-element list into coordinator
 * elements (rendered bare) and sub-agent runs (rendered in a box). No JSX
 * / no React — extracted from `sub-agent-group.tsx` so the grouping
 * contract stays pure, unit-testable, and under the file-size cap
 * (meta-architect verdict 69cf6476).
 *
 * Grouping is POSITIONAL, anchored on the spawn tool-call id (`tcid`),
 * NOT on a `subagent-`/`swarm-` message-id prefix. The live stream
 * interleaves messages the prefix gate misses: the sub-agent's reasoning
 * carries a plain UUID (the bd:python-factory-ckihm gap) and its tool
 * calls are bare `tooluse_*` assistant messages (swarm nodes also emit
 * `handoff_to_agent` tool calls). A run absorbs EVERY message after the
 * spawn until the spawn's own tool-result (`role:"tool"`,
 * `toolCallId === tcid`) closes it — the deterministic "sub-agent done"
 * boundary — with defensive fallbacks for a user turn, a new spawn, or the
 * coordinator resuming first-party prose. All four SYNC spawns
 * (spawn_subagent / spawn_swarm / spawn_graph / spawn_registered_graph)
 * share this shape and are boxed identically.
 *
 * Elements are referenced by their message.id React key, never
 * cloned/re-keyed, so CopilotKit's MemoizedAssistantMessage memoization
 * is preserved (guardrail #1).
 */

import type { AssistantMessage, Message } from "@ag-ui/core";
import type { ReactElement } from "react";
import { SYNC_SPAWN_TOOL_NAMES, spawnBoxLabel } from "./sub-agent-message";

export type GroupedRun =
  | { kind: "coordinator"; key: string; element: ReactElement }
  | {
      kind: "subagent";
      key: string;
      agentId: string;
      elements: ReactElement[];
    };

/**
 * If `msg` is a SYNC spawn (spawn_subagent / spawn_swarm / spawn_graph /
 * spawn_registered_graph), return its `{label, tcid}`; else null. All four
 * form a containment box — they share the same stream shape (spawn anchor →
 * node work → spawn's own tool-result closes). `spawn_subagent_async` is
 * excluded (separate BackgroundSpawnWindow surface). The box header label is
 * tool-name aware via `spawnBoxLabel` ("Swarm · N agents" etc.).
 */
function spawnAnchor(msg: Message): { label: string; tcid: string } | null {
  if (msg.role !== "assistant") return null;
  const spawn = (msg as AssistantMessage).toolCalls?.find((tc) =>
    SYNC_SPAWN_TOOL_NAMES.has(tc.function.name),
  );
  return spawn ? { label: spawnBoxLabel(spawn), tcid: spawn.id } : null;
}

function isSubAgentTextId(id: string): boolean {
  return id.startsWith("subagent-") || id.startsWith("swarm-");
}

/**
 * Does `msg` close the open sub-agent run BEFORE itself (i.e. it belongs
 * to the coordinator, not the sub-agent)? True for a user turn, a fresh
 * spawn, or the coordinator resuming first-party prose — an assistant
 * message that has text content, carries no tool calls, and whose id is
 * not a `subagent-`/`swarm-` bubble. (The sub-agent's own prose at
 * `subagent-<tcid>` is explicitly NOT a closer.)
 */
function closesBefore(msg: Message): boolean {
  if (msg.role === "user") return true;
  if (spawnAnchor(msg)) return true;
  if (msg.role !== "assistant") return false;
  const a = msg as AssistantMessage;
  if (a.toolCalls?.length) return false;
  if (isSubAgentTextId(a.id)) return false;
  const hasText =
    typeof a.content === "string"
      ? a.content.length > 0
      : Array.isArray(a.content) && (a.content as unknown[]).length > 0;
  return hasText;
}

/**
 * Partition the flat message list into an ordered list of coordinator
 * elements (rendered bare) and sub-agent runs (rendered in a box).
 *
 * A run opens on a SYNC spawn message and absorbs EVERY subsequent
 * message until it closes:
 *   - close AFTER the spawn's own tool-result (`role:"tool"`,
 *     `toolCallId === tcid`) — the deterministic done boundary; or
 *   - close BEFORE a coordinator message (`closesBefore`) — defensive
 *     fallback if the spawn result never arrives (stream cut short).
 */
export function groupMessageElements(
  messages: Message[],
  messageElements: ReactElement[],
): GroupedRun[] {
  const elementByKey = new Map<string, ReactElement>();
  for (const el of messageElements) {
    if (el?.key != null) elementByKey.set(String(el.key), el);
  }

  const out: GroupedRun[] = [];
  let openBox: Extract<GroupedRun, { kind: "subagent" }> | null = null;
  let openTcid: string | null = null;
  // CopilotKit renders a last-ID-wins message list, but passes the original
  // list to custom children. Mirror its normalization so one React element
  // cannot be inserted twice when a producer replays a tool-use ID.
  const uniqueMessages = [...new Map(messages.map((msg) => [msg.id, msg])).values()];

  for (const msg of uniqueMessages) {
    const el = elementByKey.get(msg.id);

    // A coordinator-owned message closes the open run before itself.
    if (openBox && closesBefore(msg)) {
      openBox = null;
      openTcid = null;
    }

    const anchor = spawnAnchor(msg);
    if (anchor) {
      openBox = {
        kind: "subagent",
        key: msg.id,
        agentId: anchor.label,
        elements: [],
      };
      openTcid = anchor.tcid;
      out.push(openBox);
      if (el) openBox.elements.push(el);
      continue;
    }

    if (openBox) {
      if (el) openBox.elements.push(el);
      // The spawn's own tool-result is the done boundary — close AFTER it.
      const m = msg as { role: string; toolCallId?: string };
      if (m.role === "tool" && m.toolCallId === openTcid) {
        openBox = null;
        openTcid = null;
      }
      continue;
    }

    // Coordinator message — rendered bare.
    if (el) out.push({ kind: "coordinator", key: msg.id, element: el });
  }
  return out;
}
