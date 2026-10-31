import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import type { Message } from "@ag-ui/core";
import { useAutoTitle } from "../use-auto-title";

const mocks = vi.hoisted(() => ({ generateSessionTitle: vi.fn() }));
vi.mock("@/components/operations/sessions/session-actions", () => ({
  generateSessionTitle: (...args: unknown[]) => mocks.generateSessionTitle(...args),
}));

const SESSION = {
  session_id: "s1", thread_id: "t1", title: "New session", agent_id: "a",
  model: "m", updated_at: "2026-09-13T00:00:00Z", archived_at: null,
  revision: 5, crew_id: "", memory_scope: "", pinned_rank: null,
  unread: false, tags: [] as string[],
  pinned_message_ids: [] as string[],
  summary: "", folder: "",
};

const userMsg: Message = { id: "1", role: "user", content: "fix the deploy" } as Message;
const assistantMsg: Message = { id: "2", role: "assistant", content: "done" } as Message;

beforeEach(() => mocks.generateSessionTitle.mockReset().mockResolvedValue({}));

describe("useAutoTitle", () => {
  it("fires generateSessionTitle once the assistant has replied and the run finished", () => {
    renderHook(() => useAutoTitle(SESSION, [userMsg, assistantMsg], false));
    expect(mocks.generateSessionTitle).toHaveBeenCalledWith(
      "s1", "user: fix the deploy\nassistant: done", 5,
    );
  });

  it("also fires when the title is the ensure_thread first-line fallback (the real Welcome-flow chat path)", () => {
    const session = { ...SESSION, title: "fix the deploy" };
    renderHook(() => useAutoTitle(session, [userMsg, assistantMsg], false));
    expect(mocks.generateSessionTitle).toHaveBeenCalledWith(
      "s1", "user: fix the deploy\nassistant: done", 5,
    );
  });

  it("does not fire while the turn is still running", () => {
    renderHook(() => useAutoTitle(SESSION, [userMsg, assistantMsg], true));
    expect(mocks.generateSessionTitle).not.toHaveBeenCalled();
  });

  it("does not fire before an assistant reply exists", () => {
    renderHook(() => useAutoTitle(SESSION, [userMsg], false));
    expect(mocks.generateSessionTitle).not.toHaveBeenCalled();
  });

  it("does not fire when the title is a real generated or manually chosen title", () => {
    renderHook(() => useAutoTitle({ ...SESSION, title: "Deploy pipeline fix" }, [userMsg, assistantMsg], false));
    expect(mocks.generateSessionTitle).not.toHaveBeenCalled();
  });

  it("fires only once per session even if messages change again", () => {
    const { rerender } = renderHook(
      ({ messages }: { messages: Message[] }) => useAutoTitle(SESSION, messages, false),
      { initialProps: { messages: [userMsg, assistantMsg] } },
    );
    rerender({ messages: [userMsg, assistantMsg, { id: "3", role: "user", content: "more" } as Message] });
    expect(mocks.generateSessionTitle).toHaveBeenCalledTimes(1);
  });

  it("calls onGenerated after a successful generation", async () => {
    const onGenerated = vi.fn();
    renderHook(() => useAutoTitle(SESSION, [userMsg, assistantMsg], false, onGenerated));
    await vi.waitFor(() => expect(onGenerated).toHaveBeenCalled());
  });
});
