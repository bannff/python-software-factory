"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Archive, ChevronDown, ChevronUp, MessageSquare, Pin, Plus, Search } from "lucide-react";
import { useSessionList, type SessionSummary } from "@/lib/hooks/use-session-list";
import { setSessionPinned } from "@/components/operations/sessions/session-actions";
import { useSessionRuntime } from "@/lib/hooks/use-session-runtime";
import { useAutoTitle } from "@/lib/hooks/use-auto-title";
import { usePersonas } from "@/lib/hooks/use-personas";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

function relativeTime(value: string): string {
  const seconds = Math.max(0, (Date.now() - Date.parse(value)) / 1000);
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function SessionRow({ session, agentName, active, onSelect, onPin, pinning }: {
  session: SessionSummary; agentName: string; active: boolean;
  onSelect: () => void; onPin: () => void; pinning: boolean;
}) {
  const pinned = session.pinned_rank !== null;
  return (
    <div className={cn("flex items-center rounded-md", active && "bg-accent/30")}>
      <button data-session-row={session.session_id} aria-current={active ? "true" : undefined}
        onClick={onSelect} className={cn("min-w-0 flex-1 rounded-md px-2 py-1.5 text-left transition-colors",
          "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          active ? "text-foreground" : "hover:bg-accent/15")}>
        <span className="flex items-center gap-1.5">
          <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full",
            active ? "bg-primary" : session.unread ? "bg-violet-400" : "bg-muted-foreground/30")} />
          <span className="truncate text-xs font-semibold">{session.title}</span>
          {pinned && <Pin className="h-3 w-3 shrink-0 fill-current text-violet-400" />}
        </span>
        <span className="mt-0.5 block truncate pl-3 text-[10px] text-muted-foreground">
          {agentName} · {relativeTime(session.updated_at)}
        </span>
      </button>
      <button type="button" onClick={onPin} disabled={pinning}
        aria-label={`${pinned ? "Unpin" : "Pin"} ${session.title}`}
        className="mr-1 rounded p-1 text-muted-foreground hover:bg-accent/30 hover:text-violet-400 disabled:opacity-40">
        <Pin className={cn("h-3 w-3", pinned && "fill-current text-violet-400")} />
      </button>
    </div>
  );
}

export function SessionDeck({ agentId }: { agentId: string }) {
  const { agent, resumeSession, createSession } = useSessionRuntime(agentId);
  const { personas } = usePersonas();
  const [expanded, setExpanded] = useState(false);
  const [archived, setArchived] = useState(false);
  const [query, setQuery] = useState("");
  const [switching, setSwitching] = useState<string | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const [pinning, setPinning] = useState<string | null>(null);
  const switchRevision = useRef(0);
  const deckRef = useRef<HTMLDivElement>(null);
  const { sessions, loading, error, refresh } = useSessionList(archived);
  const agentNames = useMemo(
    () => new Map(personas.map((persona) => [persona.id, persona.name])),
    [personas],
  );
  useEffect(() => {
    if (!agent.isRunning && agent.messages.length > 0) void refresh();
  }, [agent.isRunning, agent.messages.length, refresh]);
  const active = sessions.find((session) => session.thread_id === agent.threadId);
  useAutoTitle(active, agent.messages, agent.isRunning, refresh);
  const visible = useMemo(() => sessions.filter((session) =>
    session.title.toLowerCase().includes(query.trim().toLowerCase())), [sessions, query]);
  const recent = active ? [active, ...visible.filter((item) => item !== active)] : visible;

  const select = async (session: SessionSummary) => {
    const revision = ++switchRevision.current;
    setSwitching(session.thread_id);
    setSwitchError(null);
    try {
      const resumed = await resumeSession(session);
      if (revision !== switchRevision.current) return;
      if (resumed) setExpanded(false);
    } catch {
      if (revision === switchRevision.current) setSwitchError("Couldn’t load this conversation. Try again.");
    } finally {
      if (revision === switchRevision.current) setSwitching(null);
    }
  };
  const create = async () => {
    switchRevision.current += 1;
    setSwitchError(null);
    try {
      await createSession();
      setExpanded(false);
      requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>("textarea")?.focus());
    } catch (error) {
      setSwitchError(error instanceof Error
        ? error.message
        : "Couldn’t start the default crew. Review its configuration and retry.");
    }
  };
  const pin = async (session: SessionSummary) => {
    setPinning(session.session_id);
    setSwitchError(null);
    try {
      await setSessionPinned(
        session.session_id, session.pinned_rank === null, session.revision,
      );
      await refresh();
    } catch (error) {
      setSwitchError(error instanceof Error ? error.message : "Couldn’t update this pin.");
    } finally {
      setPinning(null);
    }
  };
  const onKeys = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const rows = [...(deckRef.current?.querySelectorAll<HTMLButtonElement>("[data-session-row]") ?? [])];
    const index = rows.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "ArrowDown" ? Math.min(rows.length - 1, index + 1) : Math.max(0, index - 1);
    if (rows[next]) { event.preventDefault(); rows[next].focus(); }
  };

  return (
    <div ref={deckRef} onKeyDown={onKeys} className="border-b border-border/30">
      <button
        aria-expanded={expanded} aria-label={expanded ? "Hide sessions" : "Show sessions"}
        onClick={() => setExpanded((value) => !value)}
        className="flex h-7 w-full items-center gap-2 px-3 text-left text-[11px] text-muted-foreground hover:bg-accent/10"
      >
        <MessageSquare className="h-3 w-3" />
        <span className="min-w-0 flex-1 truncate text-foreground/80">{active?.title ?? "Sessions"}</span>
        <span>{sessions.length}</span>
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {expanded && (
        <div className="max-h-[188px] overflow-y-auto border-t border-border/30 bg-card/20 p-2">
          <TooltipProvider delayDuration={150}>
            <div className="mb-2 flex items-center gap-1.5">
              <Tooltip><TooltipTrigger asChild>
                <label className="flex h-7 min-w-0 flex-1 items-center gap-1.5 rounded-md border border-border/50 bg-background/40 px-2">
                  <Search className="h-3 w-3 text-muted-foreground" />
                  <input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Search sessions"
                    placeholder="Search sessions…" className="min-w-0 flex-1 bg-transparent text-[11px] outline-none" />
                </label>
              </TooltipTrigger><TooltipContent side="bottom" className="text-xs">Search sessions</TooltipContent></Tooltip>
              <Tooltip><TooltipTrigger asChild>
                <button onClick={() => setArchived((value) => !value)} aria-pressed={archived} aria-label="Show archived sessions"
                  className={cn("rounded-md p-1.5 text-muted-foreground hover:bg-accent/20", archived && "bg-accent/25 text-foreground")}>
                  <Archive className="h-3.5 w-3.5" />
                </button>
              </TooltipTrigger><TooltipContent side="bottom" className="text-xs">Show archived sessions</TooltipContent></Tooltip>
              <Tooltip><TooltipTrigger asChild>
                <button onClick={() => void create()} aria-label="New session" className="rounded-md p-1.5 text-primary hover:bg-accent/20">
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </TooltipTrigger><TooltipContent side="bottom" className="text-xs">New session</TooltipContent></Tooltip>
            </div>
          </TooltipProvider>
          {switching && <p role="status" className="px-2 pb-1 text-[11px] text-muted-foreground">Loading conversation…</p>}
          {switchError && <p role="alert" className="px-2 pb-1 text-[11px] text-destructive">{switchError}</p>}
          {loading ? <p className="px-2 py-3 text-[11px] text-muted-foreground">Loading sessions…</p>
            : error ? <p role="alert" className="px-2 py-3 text-[11px] text-destructive">{error}</p>
            : recent.length === 0 ? <p className="px-2 py-3 text-[11px] text-muted-foreground">No saved sessions yet. Start a chat to create one.</p>
            : <div className="grid grid-cols-2 gap-1 max-[520px]:grid-cols-1">
                {recent.map((session, index) => <div key={session.session_id} className={index === 0 && active ? "col-span-2 max-[520px]:col-span-1" : ""}>
                  <SessionRow session={session}
                    agentName={agentNames.get(session.agent_id) ?? session.agent_id.replaceAll("-", " ")}
                    active={session === active} onSelect={() => select(session)}
                    onPin={() => void pin(session)} pinning={pinning === session.session_id} />
                </div>)}
              </div>}
        </div>
      )}
    </div>
  );
}
