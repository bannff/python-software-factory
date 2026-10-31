"use client";

import { useState } from "react";
import type { SessionSummary } from "@/lib/hooks/use-session-list";
import { loadSessionHistory } from "@/lib/hooks/use-session-history";
import { archiveSession, deleteSession, forkSession, generateSessionSummary, movePinnedSession, renameSession, reopenSession, setSessionFolder, setSessionPinned, setSessionTags } from "./session-actions";

export type SessionDetailBusy =
  "resume" | "pin" | "tags" | "reorder" | "rename" | "archive" | "reopen" | "delete" | "fork" | "summary" | "folder" | null;

/**
 * Action-handler state for ``SessionDetail``, split out to keep that
 * component under the 200 LOC ceiling once the fork control (row 14,
 * feature-map) pushed it over. Owns busy/error state and every mutating
 * call; the component owns rendering and its own editing/tag-draft state.
 */
export function useSessionDetailActions(
  session: SessionSummary,
  onChanged: (session: SessionSummary) => void,
  onDeleted?: (sessionId: string) => void,
  onForked?: (session: SessionSummary) => void,
  onResume?: (session: SessionSummary) => void | Promise<void>,
) {
  const [busy, setBusy] = useState<SessionDetailBusy>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (
    kind: Exclude<SessionDetailBusy, null>, call: () => Promise<SessionSummary>,
  ) => {
    setBusy(kind);
    setError(null);
    try {
      onChanged(await call());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setBusy(null);
    }
  };

  const resume = async () => {
    if (!onResume) return;
    setBusy("resume");
    setError(null);
    try {
      await onResume(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t resume this session.");
    } finally {
      setBusy(null);
    }
  };

  const confirmDelete = async (onCancelConfirm: () => void) => {
    setBusy("delete");
    setError(null);
    try {
      await deleteSession(session.session_id, session.revision);
      onDeleted?.(session.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t delete this session.");
      onCancelConfirm();
    } finally {
      setBusy(null);
    }
  };

  const fork = async () => {
    setBusy("fork");
    setError(null);
    try {
      onForked?.(await forkSession(session.session_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t fork this session.");
    } finally {
      setBusy(null);
    }
  };

  /** Row 18 (feature-map) — load this session's real transcript, build a
   * role-tagged excerpt, and generate/regenerate the rolling summary. The
   * session brick never sees the transcript; the FE supplies it, exactly
   * like auto-title generation. */
  const generateSummary = async () => {
    setBusy("summary");
    setError(null);
    try {
      const messages = await loadSessionHistory(session.session_id);
      const excerpt = messages
        .filter((message) => message.role === "user" || message.role === "assistant")
        .map((message) => `${message.role}: ${typeof message.content === "string" ? message.content : ""}`)
        .join("\n")
        .trim()
        .slice(0, 24_000);
      if (!excerpt) {
        setError("This session has no conversation to summarize yet.");
        return;
      }
      onChanged(await generateSessionSummary(session.session_id, excerpt, session.revision));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t summarize this session.");
    } finally {
      setBusy(null);
    }
  };

  return {
    busy, error, setError, run, resume, confirmDelete, fork, generateSummary,
    rename: (title: string) => run("rename", () => renameSession(session.session_id, title, session.revision)),
    pin: () => run("pin", () => setSessionPinned(session.session_id, session.pinned_rank === null, session.revision)),
    reorder: (beforeId: string | null) => run("reorder", () => movePinnedSession(session.session_id, beforeId, session.revision)),
    archive: () => run("archive", () => archiveSession(session.session_id, session.revision)),
    reopen: () => run("reopen", () => reopenSession(session.session_id, session.revision)),
    saveTags: (tags: string[]) => run("tags", () => setSessionTags(session.session_id, tags, session.revision)),
    saveFolder: (folder: string) => run("folder", () => setSessionFolder(session.session_id, folder, session.revision)),
  };
}
