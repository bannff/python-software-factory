"use client";

import { useEffect, useRef, useState } from "react";
import { Archive, ArchiveRestore, ArrowDown, ArrowUp, Check, FileText, Folder, Pencil, Pin, Play, Tag, X } from "lucide-react";
import type { SessionSummary } from "@/lib/hooks/use-session-list";
import { agentLabel, isArchived, relativeTime } from "./session-format";
import { DeleteSessionControl } from "./delete-session-control";
import { ForkSessionControl } from "./fork-session-control";
import { Field } from "./session-detail-field";
import { useSessionDetailActions } from "./use-session-detail-actions";

/**
 * Right-pane detail for the selected session. The heading is the session
 * title (never a raw id) and is programmatically focusable so a deep-link /
 * keyboard entry can land on it. Rename, archive, and reopen call the real
 * revision-fenced MCP tools; resume is delegated to the runtime owner so this
 * view never duplicates SessionDeck's agent/thread state.
 */
export function SessionDetail({ session, agentName, active, focusHeading, onFocusHandled, onResume, onChanged, onDeleted, onForked,
  moveUpBeforeId, moveDownBeforeId }: {
  session: SessionSummary;
  agentName?: string;
  active: boolean;
  focusHeading: boolean;
  onFocusHandled?: () => void;
  onResume?: (session: SessionSummary) => void | Promise<void>;
  onChanged: (session: SessionSummary) => void;
  /** Fired after a successful hard delete — the session no longer exists,
   * so the caller must clear any selection pointing at it (distinct from
   * onChanged, which still has a real updated record to show). */
  onDeleted?: (sessionId: string) => void;
  /** Fired after a successful fork (row 14, feature-map) with the NEW
   * child session — distinct from onChanged, since the source session is
   * untouched and the caller likely wants to select the new one. */
  onForked?: (session: SessionSummary) => void;
  moveUpBeforeId?: string;
  moveDownBeforeId?: string | null;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.title);
  const [tagDraft, setTagDraft] = useState(session.tags.join(", "));
  const [folderDraft, setFolderDraft] = useState(session.folder ?? "");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const archived = isArchived(session);
  const { busy, error, setError, rename, resume, confirmDelete, fork, generateSummary, pin, reorder, archive, reopen, saveTags, saveFolder } =
    useSessionDetailActions(session, onChanged, onDeleted, onForked, onResume);

  useEffect(() => {
    setEditing(false); setError(null); setDraft(session.title);
    setTagDraft(session.tags.join(", ")); setConfirmingDelete(false);
    setFolderDraft(session.folder ?? "");
  }, [session.session_id, session.tags, session.title, session.folder, setError]);
  useEffect(() => {
    if (focusHeading) { headingRef.current?.focus(); onFocusHandled?.(); }
  }, [focusHeading, session.session_id, onFocusHandled]);

  const saveRename = async () => {
    await rename(draft);
    setEditing(false);
  };

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-4 rounded-xl border border-border/60 bg-card/20 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        {editing ? (
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <input autoFocus aria-label="Session name" value={draft} maxLength={200}
              onChange={(event) => setDraft(event.target.value)}
              className="min-w-0 flex-1 rounded-md border border-border/60 bg-background/60 px-2.5 py-1.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <button type="button" aria-label="Save name" disabled={busy === "rename"}
              onClick={() => void saveRename()}
              className="rounded-md p-1.5 text-emerald-400 hover:bg-accent/20 disabled:opacity-50"><Check className="h-4 w-4" /></button>
            <button type="button" aria-label="Cancel rename" onClick={() => { setEditing(false); setDraft(session.title); }}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-accent/20"><X className="h-4 w-4" /></button>
          </div>
        ) : (
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Session</p>
            <h2 ref={headingRef} tabIndex={-1} title={session.title}
              className="mt-1 truncate text-xl font-semibold tracking-tight outline-none focus-visible:ring-2 focus-visible:ring-ring">
              {session.title}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {agentLabel(session, agentName)} · updated {relativeTime(session.updated_at)}
              {active && <span className="ml-2 text-emerald-400">· active now</span>}
              {archived && <span className="ml-2">· archived</span>}
            </p>
          </div>
        )}
      </div>

      <dl className="grid gap-2 border-t border-border/40 pt-4 text-sm sm:grid-cols-2">
        <Field label="Model" value={session.model} />
        <Field label="Crew" value={session.crew_id || "—"} />
        <Field label="Memory scope" value={session.memory_scope || "—"} />
      </dl>

      {!archived && <div className="flex items-center gap-2">
        <Tag className="h-3.5 w-3.5 text-muted-foreground" />
        <input aria-label="Session tags" value={tagDraft} maxLength={263}
          onChange={(event) => setTagDraft(event.target.value)} placeholder="tags, comma-separated"
          className="min-w-0 flex-1 rounded-md border border-border/60 bg-background/50 px-2.5 py-1.5 text-xs outline-none" />
        <button type="button" disabled={busy !== null} onClick={() => {
          const tags = [...new Set(tagDraft.split(",").map((tag) => tag.trim().toLowerCase()).filter(Boolean))];
          void saveTags(tags);
        }} className="rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50">Save tags</button>
      </div>}

      {!archived && <div className="flex items-center gap-2">
        <Folder className="h-3.5 w-3.5 text-muted-foreground" />
        <input aria-label="Session folder" value={folderDraft} maxLength={64}
          onChange={(event) => setFolderDraft(event.target.value)} placeholder="folder (blank = unfiled)"
          className="min-w-0 flex-1 rounded-md border border-border/60 bg-background/50 px-2.5 py-1.5 text-xs outline-none" />
        <button type="button" disabled={busy !== null} onClick={() => void saveFolder(folderDraft.trim())}
          className="rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50">Save folder</button>
      </div>}

      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}

      <section aria-label="Session summary" className="flex flex-col gap-2 border-t border-border/40 pt-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.15em] text-muted-foreground">
            <FileText className="h-3.5 w-3.5" /> Summary
          </div>
          <button type="button" disabled={busy !== null} onClick={() => void generateSummary()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-2.5 py-1 text-xs hover:bg-muted/50 disabled:opacity-50">
            {busy === "summary" ? "Summarizing…" : session.summary ? "Regenerate summary" : "Generate summary"}
          </button>
        </div>
        {session.summary ? (
          <p className="whitespace-pre-wrap text-sm text-muted-foreground">{session.summary}</p>
        ) : (
          <p className="text-sm italic text-muted-foreground/70">
            No summary yet — generate one to capture the key points of this conversation.
          </p>
        )}
      </section>

      <div className="flex flex-wrap gap-2 border-t border-border/40 pt-4">
        {onResume && !archived && (
          <button type="button" onClick={() => void resume()} disabled={busy === "resume"}
            className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500/90 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-500 disabled:opacity-50">
            <Play className="h-3.5 w-3.5" /> {busy === "resume" ? "Resuming…" : active ? "Go to conversation" : "Resume"}
          </button>
        )}
        {!archived && <button type="button" disabled={busy !== null}
          onClick={() => void pin()} aria-label={session.pinned_rank === null ? "Pin session" : "Unpin session"}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50">
          <Pin className="h-3.5 w-3.5" /> {session.pinned_rank === null ? "Pin" : "Unpin"}
        </button>}
        {session.pinned_rank !== null && moveUpBeforeId !== undefined && <button type="button"
          disabled={busy !== null} onClick={() => void reorder(moveUpBeforeId)}
          aria-label="Move pinned session up" className="rounded-lg border border-border/60 p-1.5 hover:bg-muted/50 disabled:opacity-50">
          <ArrowUp className="h-3.5 w-3.5" />
        </button>}
        {session.pinned_rank !== null && moveDownBeforeId !== undefined && <button type="button"
          disabled={busy !== null} onClick={() => void reorder(moveDownBeforeId)}
          aria-label="Move pinned session down" className="rounded-lg border border-border/60 p-1.5 hover:bg-muted/50 disabled:opacity-50">
          <ArrowDown className="h-3.5 w-3.5" />
        </button>}
        {!editing && (
          <button type="button" onClick={() => setEditing(true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">
            <Pencil className="h-3.5 w-3.5" /> Rename
          </button>
        )}
        {archived ? (
          <button type="button" disabled={busy === "reopen"}
            onClick={() => void reopen()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50">
            <ArchiveRestore className="h-3.5 w-3.5" /> Reopen
          </button>
        ) : (
          <button type="button" disabled={busy === "archive"}
            onClick={() => void archive()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/50 disabled:opacity-50">
            <Archive className="h-3.5 w-3.5" /> Archive
          </button>
        )}
        <ForkSessionControl busy={busy === "fork"} onFork={() => void fork()} />
        <DeleteSessionControl confirming={confirmingDelete} busy={busy === "delete"}
          onArm={() => setConfirmingDelete(true)}
          onConfirm={() => void confirmDelete(() => setConfirmingDelete(false))}
          onCancel={() => setConfirmingDelete(false)} />
      </div>
    </div>
  );
}