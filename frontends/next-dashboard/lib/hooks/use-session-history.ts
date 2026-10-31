"use client";

import type { Message } from "@ag-ui/core";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

type RawMessage = {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_calls: Array<{
    id: string; type: "function";
    function: { name: string; arguments: string };
  }>;
  tool_call_id: string | null;
};

export function parseSessionHistory(raw: unknown): Message[] {
  const data = unwrapToolData(raw) as { messages?: unknown };
  if (!data || !Array.isArray(data.messages)) return [];
  return data.messages.flatMap((value): Message[] => {
    if (!value || typeof value !== "object") return [];
    const item = value as RawMessage;
    if (typeof item.id !== "string" || typeof item.content !== "string") return [];
    if (item.role === "assistant") return [{
      id: item.id, role: "assistant", content: item.content,
      toolCalls: Array.isArray(item.tool_calls) ? item.tool_calls : [],
    } as Message];
    if (item.role === "tool") return [{
      id: item.id, role: "tool", content: item.content,
      toolCallId: item.tool_call_id ?? "",
    } as Message];
    if (item.role === "user" || item.role === "system") return [{
      id: item.id, role: item.role, content: item.content,
    } as Message];
    return [];
  });
}

export async function loadSessionHistory(sessionId: string): Promise<Message[]> {
  return parseSessionHistory(await callTool("agent_session_history", { session_id: sessionId }));
}
