import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import { parseSession, type SessionSummary } from "@/lib/hooks/use-session-list";

type Caller = typeof callTool;

/**
 * Thin wrappers over the session brick's real, ambient-authorized MCP tools.
 *
 * Identity is resolved server-side from the transport envelope — these calls
 * pass NO tenant/owner args. Every mutation is optimistic-concurrency fenced
 * with `expected_revision` (the CAS token from the row the user acted on) so a
 * stale write is rejected by the backend instead of silently clobbering. All
 * failures are normalized to a short, human message; the raw envelope error
 * (which can carry internal detail) is never surfaced verbatim.
 */

async function mutate(
  tool: string, args: Record<string, unknown>, failure: string, caller: Caller,
): Promise<SessionSummary> {
  try {
    return parseSession(await caller(tool, args));
  } catch {
    throw new Error(failure);
  }
}

/** Rename a session, fenced on its current revision. */
export function renameSession(
  sessionId: string, title: string, expectedRevision: number, caller: Caller = callTool,
): Promise<SessionSummary> {
  const trimmed = title.trim();
  if (!trimmed) return Promise.reject(new Error("A session needs a name."));
  return mutate(
    "session_rename",
    { session_id: sessionId, title: trimmed, expected_revision: expectedRevision },
    "Couldn’t rename this session. It may have changed elsewhere — refresh and retry.",
    caller,
  );
}

/** Auto-generate a session title from a short excerpt (row 17, feature-map
 * — the automatic half of manual rename above). Fire-and-forget by design:
 * the caller does not need to block on this or show its own error state,
 * since a failed generation just leaves the placeholder title in place. */
export function generateSessionTitle(
  sessionId: string, excerpt: string, expectedRevision: number, caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_generate_title",
    { session_id: sessionId, excerpt, expected_revision: expectedRevision },
    "Couldn’t generate a title for this session.",
    caller,
  );
}

/** Generate (or regenerate) the session's rolling conversation summary
 * (row 18, feature-map) from a transcript excerpt the caller supplies —
 * the read/regenerate surface upstream exposes as the chat Summary tab.
 * Fenced on the session's current revision; the generated summary is
 * returned on the refreshed session record (``session.summary``). */
export function generateSessionSummary(
  sessionId: string, excerpt: string, expectedRevision: number, caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_generate_summary",
    { session_id: sessionId, excerpt, expected_revision: expectedRevision },
    "Couldn’t summarize this session. It may have changed elsewhere — refresh and retry.",
    caller,
  );
}

/** Archive a session, fenced on its current revision. */
export function archiveSession(
  sessionId: string, expectedRevision: number, caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_archive",
    { session_id: sessionId, expected_revision: expectedRevision },
    "Couldn’t archive this session. It may have changed elsewhere — refresh and retry.",
    caller,
  );
}

/** Reopen (unarchive) a session, fenced on its current revision. */
export function reopenSession(
  sessionId: string, expectedRevision: number, caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_reopen",
    { session_id: sessionId, expected_revision: expectedRevision },
    "Couldn’t reopen this session. It may have changed elsewhere — refresh and retry.",
    caller,
  );
}

/** Hard-delete a session (row 8, feature-map — "Older sessions" per-session
 * delete), fenced on its current revision. Distinct from archive: this is
 * permanent and cannot be undone via reopen. */
export async function deleteSession(
  sessionId: string, expectedRevision: number, caller: Caller = callTool,
): Promise<void> {
  try {
    const raw = await caller("session_delete", {
      session_id: sessionId, expected_revision: expectedRevision,
    });
    const data = unwrapToolData(raw) as { deleted?: boolean } | null;
    if (!data?.deleted) throw new Error("not deleted");
  } catch {
    throw new Error("Couldn’t delete this session. It may have changed elsewhere — refresh and retry.");
  }
}

/** Branch a new session from an existing transcript (row 14, feature-map).
 * The child carries the source's exact bindings (mode/crew/memory scope/
 * agent/model) per upstream's own contract. Two real MCP calls, matching
 * the brick-ownership split: ``session_fork`` (session brick) creates the
 * new session ROW; ``session_fork_transcript`` (agent brick) then copies
 * the actual LangGraph checkpoint history onto it, since only the agent
 * brick's chat adapter can reach that store. The row still exists even if
 * the transcript copy fails (a real, if degraded, fork), so a transcript
 * failure is swallowed rather than thrown — the caller gets the new
 * session either way. */
export async function forkSession(
  sessionId: string, caller: Caller = callTool,
): Promise<SessionSummary> {
  let forked: SessionSummary;
  try {
    forked = parseSession(await caller("session_fork", { session_id: sessionId }));
  } catch {
    throw new Error("Couldn’t fork this session. Refresh and retry.");
  }
  try {
    await caller("session_fork_transcript", {
      source_session_id: sessionId, target_session_id: forked.session_id,
    });
  } catch {
    // The session row is real either way; a transcript-copy failure just
    // means the fork starts empty instead of matching the source. Not
    // thrown, so the caller still gets the (degraded) fork it asked for.
  }
  return forked;
}

/** Preview how many archived sessions bulk "Delete all" would remove
 * (upstream's clearable count). */
export async function countClearableSessions(caller: Caller = callTool): Promise<number> {
  try {
    const raw = await caller("session_count_archived", {});
    const data = unwrapToolData(raw) as { count?: number } | null;
    return typeof data?.count === "number" ? data.count : 0;
  } catch {
    return 0;
  }
}

/** Bulk-delete every archived session for the caller (row 8, feature-map
 * — "Older sessions" Delete all). No revision fencing, matching upstream's
 * own blanket-delete shape. Returns the number actually removed. */
export async function clearArchivedSessions(caller: Caller = callTool): Promise<number> {
  try {
    const raw = await caller("session_clear_archived", {});
    const data = unwrapToolData(raw) as { deleted_count?: number } | null;
    return typeof data?.deleted_count === "number" ? data.deleted_count : 0;
  } catch {
    throw new Error("Couldn’t clear archived sessions. Refresh and retry.");
  }
}

/** Pin or unpin a Session; new pins append after existing pinned Sessions. */
export function setSessionPinned(
  sessionId: string, pinned: boolean, expectedRevision: number,
  caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_set_pinned",
    { session_id: sessionId, pinned, expected_revision: expectedRevision },
    `Couldn’t ${pinned ? "pin" : "unpin"} this session. Refresh and retry.`,
    caller,
  );
}

/** Move one pinned Session before another; null moves it to the pinned tail. */
export function movePinnedSession(
  sessionId: string, beforeSessionId: string | null, expectedRevision: number,
  caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_move_pinned",
    { session_id: sessionId, before_session_id: beforeSessionId,
      expected_revision: expectedRevision },
    "Couldn’t reorder pinned sessions. Refresh and retry.",
    caller,
  );
}

/** Replace bounded Session tag membership. */
export function setSessionFolder(
  sessionId: string, folder: string, expectedRevision: number, caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_set_folder",
    { session_id: sessionId, folder: folder.trim(), expected_revision: expectedRevision },
    "Couldn’t update this session’s folder. Refresh and retry.",
    caller,
  );
}

export function setSessionTags(
  sessionId: string, tags: string[], expectedRevision: number,
  caller: Caller = callTool,
): Promise<SessionSummary> {
  return mutate(
    "session_set_tags",
    { session_id: sessionId, tags, expected_revision: expectedRevision },
    "Couldn’t update session tags. Refresh and retry.",
    caller,
  );
}
