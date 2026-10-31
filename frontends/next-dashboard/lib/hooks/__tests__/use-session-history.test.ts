import { describe, expect, it, vi } from "vitest";
import { loadSessionHistory, parseSessionHistory } from "../use-session-history";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => callTool(...args) }));

const messages = [
  { id: "u1", role: "user", content: "hello", tool_calls: [], tool_call_id: null },
  { id: "a1", role: "assistant", content: "", tool_calls: [{
    id: "c1", type: "function", function: { name: "lookup", arguments: "{}" },
  }], tool_call_id: null },
  { id: "t1", role: "tool", content: "found", tool_calls: [], tool_call_id: "c1" },
];

describe("session history", () => {
  it("preserves AG-UI roles, IDs, tool calls, and results", () => {
    const parsed = parseSessionHistory({ ok: true, data: { messages } });
    expect(parsed).toEqual([
      { id: "u1", role: "user", content: "hello" },
      { id: "a1", role: "assistant", content: "", toolCalls: messages[1].tool_calls },
      { id: "t1", role: "tool", content: "found", toolCallId: "c1" },
    ]);
  });

  it("loads through authenticated Agent MCP", async () => {
    callTool.mockResolvedValue({ ok: true, data: { messages } });
    expect(await loadSessionHistory("s1")).toHaveLength(3);
    expect(callTool).toHaveBeenCalledWith("agent_session_history", { session_id: "s1" });
  });
});
