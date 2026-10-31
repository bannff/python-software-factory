import { describe, expect, it, vi } from "vitest";
import { togglePinnedMessage } from "../chat-pin";

const BASE = {
  session_id: "session-a", thread_id: "thread-a", title: "Chat",
  agent_id: "companion-x-default", model: "openrouter", updated_at: "2026-01-01T00:00:00Z",
  archived_at: null, revision: 3,
};

describe("togglePinnedMessage (row 9, feature-map)", () => {
  it("pins an unpinned message: resolves the session, then writes the full set + the id", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_resolve_thread", result: { session: { ...BASE, pinned_message_ids: [] } } })
      .mockResolvedValueOnce({ tool: "session_set_pinned_messages", result: { session: { ...BASE, revision: 4, pinned_message_ids: ["msg-1"] } } });
    const pinned = await togglePinnedMessage("thread-a", "msg-1", caller);
    expect(caller).toHaveBeenNthCalledWith(1, "session_resolve_thread", { thread_id: "thread-a" });
    expect(caller).toHaveBeenNthCalledWith(2, "session_set_pinned_messages", {
      session_id: "session-a", pinned_message_ids: ["msg-1"], expected_revision: 3,
    });
    expect(pinned).toBe(true);
  });

  it("unpins an already-pinned message: writes the set with the id removed", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_resolve_thread", result: { session: { ...BASE, pinned_message_ids: ["msg-1", "msg-2"] } } })
      .mockResolvedValueOnce({ tool: "session_set_pinned_messages", result: { session: { ...BASE, revision: 4, pinned_message_ids: ["msg-2"] } } });
    const pinned = await togglePinnedMessage("thread-a", "msg-1", caller);
    expect(caller).toHaveBeenNthCalledWith(2, "session_set_pinned_messages", {
      session_id: "session-a", pinned_message_ids: ["msg-2"], expected_revision: 3,
    });
    expect(pinned).toBe(false);
  });

  it("throws when the session cannot be resolved", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("API 404: session_not_found"));
    await expect(togglePinnedMessage("thread-a", "msg-1", caller)).rejects.toThrow();
  });
});
