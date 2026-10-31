"use client";

import { useEffect, useMemo, useState } from "react";
import { Archive, Loader2, Plus, RefreshCw, Search } from "lucide-react";
import { useSessionList, type SessionSummary } from "@/lib/hooks/use-session-list";
import { usePersonas } from "@/lib/hooks/use-personas";
import { cn } from "@/lib/utils";
import { SessionGroupedList } from "./session-grouped-list";
import { SessionDetail } from "./session-detail";
import { ClearArchivedControl } from "./clear-archived-control";
import { useSessionsViewDerived } from "./use-sessions-view-derived";

/**
 * M7 Option A Sessions surface — a project-native, direct list/detail view of
 * the owner's persisted sessions. The list is the shared, ambient-authorized
 * `session_list` MCP read (reused, never re-implemented); resume/create are
 * delegated to the runtime owner via props so SessionDeck's agent/thread state
 * is never duplicated here. Rename/archive/reopen run the real revision-fenced
 * MCP tools. Loading, empty, error/retry, and archived states are all truthful.
 */
export interface SessionsViewProps {
  /** Thread id of the live conversation, so the matching row reads "Active". */
  activeThreadId?: string;
  /** Delegated resume — the runtime owner rebinds agent/thread (SessionDeck semantics). */
  onResumeSession?: (session: SessionSummary) => void | Promise<void>;
  /** Delegated new-session start — the runtime owner materializes the default crew. */
  onCreateSession?: () => void | Promise<void>;
  /** Deep-link target: select this session and focus its detail heading. */
  focusSessionId?: string;
  /** Fired once the heading focus has been applied. */
  onFocusHandled?: () => void;
}

export default function SessionsView({
  activeThreadId, onResumeSession, onCreateSession, focusSessionId, onFocusHandled,
}: SessionsViewProps) {
  const [includeArchived, setIncludeArchived] = useState(false);
  const { sessions, loading, error, refresh } = useSessionList(includeArchived);
  const { personas } = usePersonas();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusPending, setFocusPending] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, SessionSummary>>({});
  const [starting, setStarting] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

  const create = async () => {
    if (!onCreateSession) return;
    setStarting(true);
    setRuntimeError(null);
    try {
      await onCreateSession();
    } catch (err) {
      setRuntimeError(err instanceof Error ? err.message : "Couldn’t start a new session.");
    } finally {
      setStarting(false);
    }
  };

  const agentNames = useMemo(
    () => new Map(personas.map((persona) => [persona.id, persona.name])),
    [personas],
  );

  const { merged, tagFilters, folderFilters, visible, groups, selected, moveUpBeforeId, moveDownBeforeId } =
    useSessionsViewDerived(sessions, overrides, query, filter, selectedId);

  // Adopt an incoming deep-link target and arm the heading focus.
  useEffect(() => {
    if (focusSessionId) { setSelectedId(focusSessionId); setFocusPending(true); }
  }, [focusSessionId]);

  // Preserve explicit/deep-link selection only; bare /sessions remains neutral.
  useEffect(() => {
    if (!loading && selectedId && !visible.some((session) => session.session_id === selectedId)) {
      setSelectedId(null);
    }
  }, [loading, selectedId, visible]);

  const onChanged = (session: SessionSummary) => {
    setOverrides((prev) => ({ ...prev, [session.session_id]: session }));
    void refresh();
  };
  const onDeleted = (sessionId: string) => {
    setSelectedId((current) => (current === sessionId ? null : current));
    void refresh();
  };
  const onForked = (session: SessionSummary) => {
    setOverrides((prev) => ({ ...prev, [session.session_id]: session }));
    setSelectedId(session.session_id);
    void refresh();
  };

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="sessions-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Operations</p>
          <h1 id="sessions-title" className="mt-1 text-2xl font-semibold tracking-tight">Sessions</h1>
          <p className="mt-1 text-sm text-muted-foreground">Your saved conversations — resume, rename, or archive any of them.</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setIncludeArchived((value) => !value)} aria-pressed={includeArchived}
            aria-label="Show archived sessions"
            className={cn("inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-2 text-xs transition-colors hover:bg-muted/50",
              includeArchived && "border-violet-500/40 bg-violet-500/[0.06] text-foreground")}>
            <Archive className="h-3.5 w-3.5" /> Archived
          </button>
          <ClearArchivedControl visible={includeArchived} onCleared={refresh} />
          <button type="button" onClick={refresh} aria-label="Refresh sessions"
            className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          </button>
          {onCreateSession && (
            <button type="button" onClick={() => void create()} disabled={starting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500/90 px-3 py-2 text-xs font-medium text-white hover:bg-violet-500 disabled:opacity-50">
              <Plus className="h-3.5 w-3.5" /> {starting ? "Starting…" : "New session"}
            </button>
          )}
        </div>
      </header>

      {runtimeError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          {runtimeError}
        </div>
      )}

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Sessions unavailable: {error}</span>
          <button type="button" onClick={refresh} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && merged.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading sessions…
        </div>
      )}

      {!error && !(loading && merged.length === 0) && (
        <div className="grid flex-1 gap-4 lg:grid-cols-[minmax(0,22rem)_1fr]">
          <div className="flex min-w-0 flex-col gap-3">
            <div className="flex gap-2" aria-label="Session filters">
              {["all", "unread", ...tagFilters.map((tag) => `tag:${tag}`), ...folderFilters.map((f) => `folder:${f}`)].map((id) => <button key={id} type="button"
                aria-pressed={filter === id} onClick={() => setFilter(id)}
                className={cn("rounded-full border px-3 py-1 text-xs",
                  filter === id ? "border-violet-500/50 bg-violet-500/10 text-violet-300" : "border-border/60 text-muted-foreground")}>{id.startsWith("tag:") ? `#${id.slice(4)}` : id.startsWith("folder:") ? `📁 ${id.slice(7)}` : id[0].toUpperCase() + id.slice(1)}</button>)}
            </div>
            <label className="flex h-9 items-center gap-2 rounded-lg border border-border/60 bg-background/40 px-2.5">
              <Search className="h-3.5 w-3.5 text-muted-foreground" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Search sessions"
                placeholder="Search sessions…" className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
            </label>
            {visible.length === 0 ? (
              <p className="rounded-xl border border-dashed border-border/60 p-6 text-center text-sm text-muted-foreground">
                {query.trim()
                  ? "No sessions match your search."
                  : includeArchived
                    ? "No sessions yet. Start a chat to create one."
                    : "No active sessions. Start a chat, or show archived sessions."}
              </p>
            ) : (
              <SessionGroupedList groups={groups} agentNames={agentNames}
                activeThreadId={activeThreadId} selectedId={selectedId}
                onSelect={(session) => { setSelectedId(session.session_id); setFocusPending(false); }} />
            )}
          </div>
          {selected ? (
            <SessionDetail session={selected} agentName={agentNames.get(selected.agent_id)}
              active={selected.thread_id === activeThreadId}
              focusHeading={focusPending && selected.session_id === focusSessionId}
              onFocusHandled={() => { setFocusPending(false); onFocusHandled?.(); }}
              onResume={onResumeSession} onChanged={onChanged} onDeleted={onDeleted} onForked={onForked}
              moveUpBeforeId={moveUpBeforeId} moveDownBeforeId={moveDownBeforeId} />
          ) : (
            <div className="hidden min-h-64 self-start items-center justify-center rounded-xl border border-border/60 bg-card/10 p-6 text-sm text-muted-foreground lg:flex">
              Select a session to see its details.
            </div>
          )}
        </div>
      )}
    </section>
  );
}
