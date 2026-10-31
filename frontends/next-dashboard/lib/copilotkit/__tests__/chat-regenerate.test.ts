import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ loadSessionHistory: vi.fn() }));
vi.mock("@/lib/hooks/use-session-history", () => ({
  loadSessionHistory: (...args: unknown[]) => mocks.loadSessionHistory(...args),
}));

import { regenerateTurn } from "../chat-regenerate";

const SESSION = {
  session_id: "session-a", thread_id: "thread-a", title: "Chat",
  agent_id: "companion-x-default", model: "openrouter", updated_at: "2026-01-01T00:00:00Z",
  archived_at: null, revision: 3,
};

const HISTORY_MESSAGES = [
  { id: "msg-1", role: "user" as const, content: "try again" },
  { id: "msg-2", role: "assistant" as const, content: "new reply", toolCalls: [] },
];

describe("regenerateTurn (row 16, feature-map)", () => {
  it("resolves the session, calls regenerate, then reflects the REAL server transcript", async () => {
    mocks.loadSessionHistory.mockReset().mockResolvedValue(HISTORY_MESSAGES);
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_resolve_thread", result: { session: SESSION } })
      .mockResolvedValueOnce({ tool: "session_regenerate", result: { ok: true, data: { checkpoint_id: "c1", regenerated: true } } });
    const result = await regenerateTurn("thread-a", "msg-1", "try again", caller);
    expect(caller).toHaveBeenNthCalledWith(1, "session_resolve_thread", { thread_id: "thread-a" });
    expect(caller).toHaveBeenNthCalledWith(2, "session_regenerate", {
      session_id: "session-a", message_id: "msg-1", new_prompt: "try again", expected_revision: 3,
    });
    expect(mocks.loadSessionHistory).toHaveBeenCalledWith("session-a");
    expect(result).toBe(HISTORY_MESSAGES);
  });

  it("returns null, not an error, when the message was never found — and never fetches history", async () => {
    mocks.loadSessionHistory.mockReset();
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_resolve_thread", result: { session: SESSION } })
      .mockResolvedValueOnce({ tool: "session_regenerate", result: { ok: true, data: { checkpoint_id: null, regenerated: false } } });
    const result = await regenerateTurn("thread-a", "msg-unknown", "try again", caller);
    expect(result).toBeNull();
    expect(caller).toHaveBeenCalledTimes(2);
    expect(mocks.loadSessionHistory).not.toHaveBeenCalled();
  });

  it("throws when the session cannot be resolved", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("API 404: session_not_found"));
    await expect(regenerateTurn("thread-a", "msg-1", "try again", caller)).rejects.toThrow();
  });
});
