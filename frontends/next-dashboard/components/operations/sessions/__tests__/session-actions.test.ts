import { describe, expect, it, vi } from "vitest";
import { archiveSession, clearArchivedSessions, countClearableSessions, deleteSession, forkSession, generateSessionSummary, generateSessionTitle, movePinnedSession, renameSession, reopenSession, setSessionFolder, setSessionPinned, setSessionTags } from "../session-actions";

const RECORD = {
  session_id: "s1", thread_id: "t1", title: "Renamed", agent_id: "companion-x-default",
  model: "openrouter/x/y", updated_at: "2026-09-13T12:00:00Z", archived_at: null,
  revision: 3, crew_id: "", memory_scope: "", pinned_rank: null as number | null,
  unread: false, tags: [] as string[], summary: "", folder: "",
};

/** callTool contract: returns the outer {tool, result:{session}} envelope. */
function ok(session = RECORD) {
  return vi.fn().mockResolvedValue({ tool: "session_x", result: { session } });
}

describe("session-actions MCP wrappers", () => {
  it("renames with the CAS revision and trimmed title, no identity args", async () => {
    const caller = ok();
    const result = await renameSession("s1", "  Renamed  ", 3, caller);
    expect(caller).toHaveBeenCalledWith("session_rename", {
      session_id: "s1", title: "Renamed", expected_revision: 3,
    });
    const args = caller.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("tenant_id");
    expect(args).not.toHaveProperty("owner_id");
    expect(result.title).toBe("Renamed");
  });

  it("rejects a blank rename before calling any tool", async () => {
    const caller = ok();
    await expect(renameSession("s1", "   ", 3, caller)).rejects.toThrow(/needs a name/i);
    expect(caller).not.toHaveBeenCalled();
  });

  it("archives with the CAS revision", async () => {
    const caller = ok();
    await archiveSession("s1", 3, caller);
    expect(caller).toHaveBeenCalledWith("session_archive", { session_id: "s1", expected_revision: 3 });
  });

  it("generates a summary with the CAS revision and excerpt, returning session.summary", async () => {
    const caller = ok({ ...RECORD, summary: "Rolling summary text" });
    const result = await generateSessionSummary("s1", "user: hi\nassistant: yo", 3, caller);
    expect(caller).toHaveBeenCalledWith("session_generate_summary", {
      session_id: "s1", excerpt: "user: hi\nassistant: yo", expected_revision: 3,
    });
    expect(result.summary).toBe("Rolling summary text");
  });

  it("files a session under a folder with the CAS revision (trimmed)", async () => {
    const caller = ok({ ...RECORD, folder: "Client work" });
    const result = await setSessionFolder("s1", "  Client work  ", 3, caller);
    expect(caller).toHaveBeenCalledWith("session_set_folder", {
      session_id: "s1", folder: "Client work", expected_revision: 3,
    });
    expect(result.folder).toBe("Client work");
  });

  it("reopens with the CAS revision", async () => {
    const caller = ok();
    await reopenSession("s1", 4, caller);
    expect(caller).toHaveBeenCalledWith("session_reopen", { session_id: "s1", expected_revision: 4 });
  });

  it("pins with the CAS revision and no identity args", async () => {
    const caller = ok({ ...RECORD, pinned_rank: 1024, revision: 4 });
    await setSessionPinned("s1", true, 3, caller);
    expect(caller).toHaveBeenCalledWith("session_set_pinned", {
      session_id: "s1", pinned: true, expected_revision: 3,
    });
  });

  it("moves a pinned session before the requested target", async () => {
    const caller = ok({ ...RECORD, pinned_rank: 512, revision: 4 });
    await movePinnedSession("s1", "s2", 3, caller);
    expect(caller).toHaveBeenCalledWith("session_move_pinned", {
      session_id: "s1", before_session_id: "s2", expected_revision: 3,
    });
  });

  it("replaces Session tags with the CAS revision", async () => {
    const caller = ok({ ...RECORD, tags: ["urgent"], revision: 4 });
    await setSessionTags("s1", ["urgent"], 3, caller);
    expect(caller).toHaveBeenCalledWith("session_set_tags", {
      session_id: "s1", tags: ["urgent"], expected_revision: 3,
    });
  });

  it("normalizes a failing tool call to a safe, non-leaky message", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("API 502: internal owner=abc detail"));
    await expect(archiveSession("s1", 3, caller)).rejects.toThrow(/It may have changed elsewhere/);
    await expect(archiveSession("s1", 3, caller)).rejects.not.toThrow(/owner=abc/);
  });

  it("normalizes an unparseable session payload to a safe message", async () => {
    const caller = vi.fn().mockResolvedValue({ tool: "session_rename", result: { session: { bogus: true } } });
    await expect(renameSession("s1", "x", 3, caller)).rejects.toThrow(/Couldn’t rename/);
  });

  it("generates a title from an excerpt with the CAS revision, no identity args", async () => {
    const caller = ok({ ...RECORD, title: "Deploy pipeline fix" });
    const result = await generateSessionTitle("s1", "user: fix deploy\nassistant: done", 3, caller);
    expect(caller).toHaveBeenCalledWith("session_generate_title", {
      session_id: "s1", excerpt: "user: fix deploy\nassistant: done", expected_revision: 3,
    });
    const args = caller.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("tenant_id");
    expect(result.title).toBe("Deploy pipeline fix");
  });

  it("deletes a session with the CAS revision, no identity args", async () => {
    const caller = vi.fn().mockResolvedValue({
      tool: "session_delete", result: { ok: true, data: { session_id: "s1", deleted: true } },
    });
    await deleteSession("s1", 3, caller);
    expect(caller).toHaveBeenCalledWith("session_delete", { session_id: "s1", expected_revision: 3 });
    const args = caller.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("tenant_id");
  });

  it("normalizes a failing delete to a safe, non-leaky message", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("API 409: revision conflict owner=abc"));
    await expect(deleteSession("s1", 3, caller)).rejects.toThrow(/It may have changed elsewhere/);
    await expect(deleteSession("s1", 3, caller)).rejects.not.toThrow(/owner=abc/);
  });

  it("throws if the tool reports deleted=false without erroring", async () => {
    const caller = vi.fn().mockResolvedValue({
      tool: "session_delete", result: { ok: true, data: { session_id: "s1", deleted: false } },
    });
    await expect(deleteSession("s1", 3, caller)).rejects.toThrow(/Couldn.t delete/);
  });

  it("previews the clearable count with no identity args", async () => {
    const caller = vi.fn().mockResolvedValue({
      tool: "session_count_archived", result: { ok: true, data: { count: 4 } },
    });
    const count = await countClearableSessions(caller);
    expect(caller).toHaveBeenCalledWith("session_count_archived", {});
    expect(count).toBe(4);
  });

  it("falls back to 0 for the clearable count on a failing call", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("boom"));
    expect(await countClearableSessions(caller)).toBe(0);
  });

  it("clears archived sessions and returns the real deleted count", async () => {
    const caller = vi.fn().mockResolvedValue({
      tool: "session_clear_archived", result: { ok: true, data: { deleted_count: 3 } },
    });
    const count = await clearArchivedSessions(caller);
    expect(caller).toHaveBeenCalledWith("session_clear_archived", {});
    expect(count).toBe(3);
  });

  it("throws a safe message if clearing archived sessions fails", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("API 500: internal owner=abc"));
    await expect(clearArchivedSessions(caller)).rejects.toThrow(/Couldn.t clear archived/);
    await expect(clearArchivedSessions(caller)).rejects.not.toThrow(/owner=abc/);
  });

  it("forks a session with just its id, then copies the transcript via the agent brick", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_fork", result: { session: { ...RECORD, session_id: "s2", title: "Original (fork)" } } })
      .mockResolvedValueOnce({ tool: "session_fork_transcript", result: { ok: true, data: { copied: true } } });
    const result = await forkSession("s1", caller);
    expect(caller).toHaveBeenNthCalledWith(1, "session_fork", { session_id: "s1" });
    expect(caller).toHaveBeenNthCalledWith(2, "session_fork_transcript", {
      source_session_id: "s1", target_session_id: "s2",
    });
    const args = caller.mock.calls[0][1] as Record<string, unknown>;
    expect(args).not.toHaveProperty("tenant_id");
    expect(args).not.toHaveProperty("expected_revision");
    expect(result.session_id).toBe("s2");
    expect(result.title).toBe("Original (fork)");
  });

  it("normalizes a failing fork to a safe, non-leaky message", async () => {
    const caller = vi.fn().mockRejectedValue(new Error("API 404: session_not_found owner=abc"));
    await expect(forkSession("s1", caller)).rejects.toThrow(/Couldn.t fork/);
    await expect(forkSession("s1", caller)).rejects.not.toThrow(/owner=abc/);
  });

  it("still returns the new session even if the transcript copy fails", async () => {
    const caller = vi.fn()
      .mockResolvedValueOnce({ tool: "session_fork", result: { session: { ...RECORD, session_id: "s2", title: "Original (fork)" } } })
      .mockRejectedValueOnce(new Error("API 500: internal owner=abc"));
    const result = await forkSession("s1", caller);
    expect(result.session_id).toBe("s2");
  });
});
