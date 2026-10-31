"use client";

/**
 * SubAgentToolRows — nested tool-call display inside the spawn_subagent card
 * (bd:python-factory-0zkj4).
 *
 * Reads agent.messages (AbstractAgent.messages: Message[] from @ag-ui/client)
 * via useAgent({ updates: [OnMessagesChanged] }) and extracts tool calls that
 * arrive after the spawn_subagent entry in the message list.
 *
 * Correlation strategy (bd:python-factory-wipnv update): when parentMessageId
 * is emitted by the backend, @ag-ui/client applyEvents places sub-agent tool
 * calls directly inside the spawn AssistantMessage.toolCalls[]. We first try
 * to read them from the spawn message directly (O(1) by spawnToolCallId prop),
 * then fall back to the positional scan for backward-compat.
 *
 * SDK source pins:
 *   @ag-ui/core AssistantMessageSchema — role:"assistant",
 *     toolCalls?: { id, type:"function", function: { name, arguments } }[]
 *   @ag-ui/client AbstractAgent.messages: Message[] — live, mutated in place
 *     by applyEvents; re-renders triggered by UseAgentUpdate.OnMessagesChanged.
 *   @copilotkitnext/react/dist/hooks/use-agent.d.mts — useAgent({ updates })
 */

import { useAgent, UseAgentUpdate } from "@copilotkit/react-core/v2";
import type { Message } from "@ag-ui/core";
import { CheckCircle2, Loader2 } from "lucide-react";
import { COMPANION_X_AGENT_ID } from "./companion-agent";

// ---- types ----------------------------------------------------------------

interface ExtractedToolCall {
  id: string;
  name: string;
  /** Raw JSON args string from the wire — non-empty when args are done. */
  args: string;
  /** True when a ToolMessage result has been added for this id. */
  complete: boolean;
}

// ---- helpers ---------------------------------------------------------------

/** Narrow an ag-ui Message to an AssistantMessage safely. */
function isAssistant(
  m: Message,
): m is Extract<Message, { role: "assistant" }> {
  return m.role === "assistant";
}

/** Narrow an ag-ui Message to a ToolMessage (role:"tool") safely. */
function isTool(m: Message): m is Extract<Message, { role: "tool" }> {
  return m.role === "tool";
}

/**
 * Extract sub-agent tool calls from agent.messages.
 *
 * Primary path (bd:python-factory-wipnv): if spawnToolCallId is provided,
 * look for an AssistantMessage that contains that toolCallId and return all
 * other non-spawn tool calls from it (they landed there via parentMessageId).
 *
 * Fallback: returns the tool calls from AssistantMessages that appear AFTER
 * the last `spawnToolName` entry, excluding spawn_ calls.
 * For each call, marks complete=true if a corresponding ToolMessage (role:
 * "tool", toolCallId) is present in the message list.
 */
function extractSubAgentToolCalls(
  messages: Message[],
  spawnToolName: string = "spawn_subagent",
  spawnToolCallId?: string,
): ExtractedToolCall[] {
  // Collect all tool-result ids for completion detection.
  const completedIds = new Set<string>();
  for (const msg of messages) {
    if (isTool(msg) && msg.toolCallId) {
      completedIds.add(msg.toolCallId);
    }
  }

  // Primary path: direct lookup by spawn toolCallId (parentMessageId nesting).
  if (spawnToolCallId) {
    for (const msg of messages) {
      if (!isAssistant(msg) || !msg.toolCalls?.length) continue;
      const hasSpawn = msg.toolCalls.some((tc) => tc.id === spawnToolCallId);
      if (!hasSpawn) continue;
      // Return non-spawn calls from this message — these are nested sub-agent calls.
      const nested: ExtractedToolCall[] = [];
      for (const tc of msg.toolCalls) {
        if (tc.id === spawnToolCallId) continue;
        if (tc.function.name.startsWith("spawn_")) continue;
        nested.push({
          id: tc.id,
          name: tc.function.name,
          args: tc.function.arguments ?? "",
          complete: completedIds.has(tc.id),
        });
      }
      if (nested.length > 0) return nested;
    }
  }

  // Fallback: positional scan after last spawn message.
  let spawnMsgIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (
      isAssistant(msg) &&
      msg.toolCalls?.some((tc) => tc.function.name === spawnToolName)
    ) {
      spawnMsgIdx = i;
      break;
    }
  }
  if (spawnMsgIdx === -1) return [];

  const result: ExtractedToolCall[] = [];
  for (let i = spawnMsgIdx + 1; i < messages.length; i++) {
    const msg = messages[i];
    if (!isAssistant(msg) || !msg.toolCalls?.length) continue;
    for (const tc of msg.toolCalls) {
      if (tc.function.name.startsWith("spawn_")) continue;
      result.push({
        id: tc.id,
        name: tc.function.name,
        args: tc.function.arguments ?? "",
        complete: completedIds.has(tc.id),
      });
    }
  }
  return result;
}

/** Format a tool name for display: underscores → spaces. */
function formatToolName(name: string): string {
  return name.replace(/_/g, " ");
}

/** Truncate an args string to a readable preview. */
function argsPreview(args: string, max = 60): string {
  if (!args) return "";
  try {
    const parsed = JSON.parse(args);
    const flat = JSON.stringify(parsed);
    return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
  } catch {
    return args.length > max ? `${args.slice(0, max - 1)}…` : args;
  }
}

// ---- component -------------------------------------------------------------

interface SubAgentToolRowsProps {
  /**
   * The spawn card's toolCallId. When provided, enables O(1) direct lookup
   * of nested sub-agent calls via parentMessageId nesting
   * (bd:python-factory-wipnv). Falls back to positional scan when absent.
   */
  spawnToolCallId?: string;
  /**
   * The spawn tool name to use as the anchor when scanning agent.messages.
   * Defaults to "spawn_subagent". Pass "spawn_swarm", "spawn_graph", or
   * "spawn_registered_graph" for the corresponding spawn card variants.
   */
  spawnToolName?: string;
}

/**
 * Renders nested tool-call rows for a spawn_* card.
 *
 * Mounted inside <ToolCallCard> children when status !== "inProgress".
 * Shows sub-agent tool calls as they stream in and marks them complete
 * once their ToolMessage result arrives.
 *
 * The `spawnToolName` prop controls which spawn tool is used as the
 * anchor in the message scan (bd:python-factory-mmrhw).
 */
export function SubAgentToolRows({
  spawnToolCallId,
  spawnToolName = "spawn_subagent",
}: SubAgentToolRowsProps) {
  const { agent } = useAgent({
    agentId: COMPANION_X_AGENT_ID,
    updates: [UseAgentUpdate.OnMessagesChanged],
  });

  const toolCalls = extractSubAgentToolCalls(
    agent.messages, spawnToolName, spawnToolCallId,
  );

  if (toolCalls.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic">
        Waiting for sub-agent tool calls…
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {toolCalls.map((tc) => (
        <SubAgentToolRow key={tc.id} toolCall={tc} />
      ))}
    </div>
  );
}

// ---- single row ------------------------------------------------------------

function SubAgentToolRow({ toolCall }: { toolCall: ExtractedToolCall }) {
  const Icon = toolCall.complete ? CheckCircle2 : Loader2;
  const iconCls = toolCall.complete
    ? "text-emerald-500"
    : "text-blue-500 animate-spin";
  const preview = toolCall.complete ? argsPreview(toolCall.args) : undefined;

  return (
    <div className="flex items-center gap-2 text-[11px] py-0.5">
      <Icon className={`h-3 w-3 shrink-0 ${iconCls}`} />
      <span className="font-mono text-foreground/80 truncate">
        {formatToolName(toolCall.name)}
      </span>
      {preview && (
        <span className="text-muted-foreground truncate ml-auto">{preview}</span>
      )}
    </div>
  );
}
