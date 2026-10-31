import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import { ChatSummaryTab } from "../chat-summary-tab";

const SESSION = {
  session_id: "s1", thread_id: "t1", title: "Chat", agent_id: "companion-x-default",
  model: "openrouter", updated_at: "2026-01-01T00:00:00Z", archived_at: null, revision: 3,
  crew_id: "", memory_scope: "", pinned_rank: null, unread: false, tags: [],
  pinned_message_ids: [], summary: "", folder: "",
};
const wrap = (data: unknown) => ({ tool: "x", result: data });

beforeEach(() => mocks.callTool.mockReset());

describe("ChatSummaryTab (row 18 — chat-panel home)", () => {
  it("shows the empty state when the resolved session has no summary", async () => {
    mocks.callTool.mockResolvedValue(wrap({ session: SESSION }));
    render(<ChatSummaryTab threadId="t1" />);
    await waitFor(() => expect(screen.getByText(/No summary yet/i)).toBeTruthy());
    expect(screen.getByRole("button", { name: "Generate" })).toBeTruthy();
  });

  it("generates from the transcript and shows the new summary", async () => {
    mocks.callTool.mockImplementation(async (tool: string) => {
      if (tool === "session_resolve_thread") return wrap({ session: SESSION });
      if (tool === "agent_session_history") return wrap({ messages: [
        { id: "m1", role: "user", content: "hi", tool_calls: [], tool_call_id: null },
        { id: "m2", role: "assistant", content: "hello", tool_calls: [], tool_call_id: null },
      ] });
      if (tool === "session_generate_summary") return wrap({ session: { ...SESSION, summary: "A greeting.", revision: 4 } });
      return wrap({});
    });
    render(<ChatSummaryTab threadId="t1" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Generate" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Generate" }));
    await waitFor(() => expect(screen.getByText("A greeting.")).toBeTruthy());
    expect(mocks.callTool).toHaveBeenCalledWith("session_generate_summary", {
      session_id: "s1", excerpt: "user: hi\nassistant: hello", expected_revision: 3,
    });
  });

  it("shows an honest error when the thread has no saved session", async () => {
    mocks.callTool.mockRejectedValueOnce(new Error("session_not_found"));
    render(<ChatSummaryTab threadId="t1" />);
    await waitFor(() => expect(screen.getByText(/isn’t saved as a session yet/i)).toBeTruthy());
  });
});
