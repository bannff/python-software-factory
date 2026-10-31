"use client";

import { Archive, Folder, MessageSquare, Pin } from "lucide-react";
import type { SessionSummary } from "@/lib/hooks/use-session-list";
import { cn } from "@/lib/utils";
import { agentLabel, isArchived, relativeTime } from "./session-format";

/**
 * One selectable session in the list rail. The title is the primary label —
 * never the raw session_id — with the resolved agent name and relative time
 * as secondary context. An archived session is visibly marked so the state is
 * truthful rather than blended in with live sessions.
 */
export function SessionCard({ session, agentName, active, selected, onSelect }: {
  session: SessionSummary;
  agentName?: string;
  active: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const archived = isArchived(session);
  return (
    <button
      type="button"
      data-session-card={session.session_id}
      aria-current={selected ? "true" : undefined}
      aria-label={`Open session ${session.title}${archived ? " (archived)" : ""}`}
      onClick={onSelect}
      className={cn(
        "group flex min-w-0 flex-col gap-1 rounded-xl border p-3 text-left transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected
          ? "border-violet-500/50 bg-violet-500/[0.06]"
          : "border-border/60 bg-card/30 hover:-translate-y-0.5 hover:border-violet-500/40 hover:bg-card/60",
      )}
    >
      <span className="flex items-center gap-2">
        <span className={cn("rounded-md p-1.5", active ? "bg-emerald-500/10 text-emerald-400" : "bg-violet-500/10 text-violet-400")}>
          <MessageSquare className="h-3.5 w-3.5" />
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium" title={session.title}>{session.title}</span>
        {session.unread && <span aria-label="Unread"
          className="h-2 w-2 shrink-0 rounded-full bg-violet-400" />}
        {session.pinned_rank !== null && (
          <span className="flex shrink-0 items-center gap-1 text-[10px] font-medium text-violet-400">
            <Pin className="h-3 w-3 fill-current" /> Pinned
          </span>
        )}
        {active && (
          <span className="shrink-0 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
            Active
          </span>
        )}
        {archived && (
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            <Archive className="h-2.5 w-2.5" /> Archived
          </span>
        )}
      </span>
      <span className="truncate pl-9 text-xs text-muted-foreground">
        {agentLabel(session, agentName)} · {relativeTime(session.updated_at)}
      </span>
      {(session.folder || session.tags.length > 0) && <span className="flex flex-wrap items-center gap-1 pl-9">
        {session.folder && <span aria-label={`Folder ${session.folder}`}
          className="flex items-center gap-1 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[9px] text-amber-300">
          <Folder className="h-2.5 w-2.5" />{session.folder}</span>}
        {session.tags.map((tag, index) => <span key={tag}
          className={cn("rounded-full px-1.5 py-0.5 text-[9px]",
            index % 2 ? "bg-sky-500/10 text-sky-300" : "bg-violet-500/10 text-violet-300")}>#{tag}</span>)}
      </span>}
    </button>
  );
}
