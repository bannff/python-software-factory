import { describe, expect, it, vi } from "vitest";
import { rewindToMessage } from "../chat-rewind";

const SESSION = {
  session_id: "session-a", thread_id: "thread-a", title: "Chat",
  agent_id: "companion-x-default", model: "openrouter", updated_at: "2026-01-01T00:00:00Z",
  archived_at: null, revision: 3,
};

describe("rewindToMessage (row 15, feature-map)", () => {
  it("resolves the session by thread id, then rewinds with its revision", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_resolve_thread", result: { session: SESSION } })
      .mockResolvedValueOnce({ tool: "session_rewind", result: { ok: true, data: { checkpoint_id: "c1", rewound: true } } });
    const result = await rewindToMessage("thread-a", "msg-1", caller);
    expect(caller).toHaveBeenNthCalledWith(1, "session_resolve_thread", { thread_id: "thread-a" });
    expect(caller).toHaveBeenNthCalledWith(2, "session_rewind", {
      session_id: "session-a", message_id: "msg-1", expected_revision: 3,
    });
    expect(result).toBe(true);
  });

  it("reports false, not an error, when the message was never found", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_resolve_thread", result: { session: SESSION } })
      .mockResolvedValueOnce({ tool: "session_rewind", result: { ok: true, data: { checkpoint_id: null, rewound: false } } });
    await expect(rewindToMessage("thread-a", "msg-unknown", caller)).resolves.toBe(false);
  });

  it("throws when the session cannot be resolved", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("API 404: session_not_found"));
    await expect(rewindToMessage("thread-a", "msg-1", caller)).rejects.toThrow();
  });
});
