import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import { ChatPinsTab } from "../chat-pins-tab";

const SESSION = (over: Record<string, unknown> = {}) => ({
  session_id: "s1", thread_id: "t1", title: "Chat", agent_id: "companion-x-default",
  model: "openrouter", updated_at: "2026-01-01T00:00:00Z", archived_at: null, revision: 3,
  crew_id: "", memory_scope: "", pinned_rank: null, unread: false, tags: [],
  pinned_message_ids: [], summary: "", folder: "", ...over,
});
const wrap = (data: unknown) => ({ tool: "x", result: data });
const HISTORY = wrap({ messages: [
  { id: "m1", role: "user", content: "pinned ask", tool_calls: [], tool_call_id: null },
  { id: "m2", role: "assistant", content: "not pinned", tool_calls: [], tool_call_id: null },
] });

beforeEach(() => mocks.callTool.mockReset());

describe("ChatPinsTab (row 9 — pins panel)", () => {
  it("shows the empty state when nothing is pinned", async () => {
    mocks.callTool.mockResolvedValue(wrap({ session: SESSION() }));
    render(<ChatPinsTab threadId="t1" />);
    await waitFor(() => expect(screen.getByText(/No pinned messages/i)).toBeTruthy());
  });

  it("lists the pinned transcript messages and unpins one", async () => {
    mocks.callTool.mockImplementation(async (tool: string) => {
      if (tool === "session_resolve_thread") return wrap({ session: SESSION({ pinned_message_ids: ["m1"] }) });
      if (tool === "agent_session_history") return HISTORY;
      if (tool === "session_set_pinned_messages") return wrap({ session: SESSION({ pinned_message_ids: [] }) });
      return wrap({});
    });
    render(<ChatPinsTab threadId="t1" />);
    await waitFor(() => expect(screen.getByText("pinned ask")).toBeTruthy());
    expect(screen.queryByText("not pinned")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Unpin m1" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_set_pinned_messages", {
      session_id: "s1", pinned_message_ids: [], expected_revision: 3,
    }));
  });
});
