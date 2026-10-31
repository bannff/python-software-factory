"use client";

import { useMemo, useState } from "react";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ALL_LIVE_STATES,
  filterAndSortRoster,
  type MemberLiveState,
  type RosterMember,
  type RosterSort,
} from "./roster-filter";

/**
 * Row 30 (feature-map) — the Crew Members roster surface (presentational).
 *
 * Composes the pure `filterAndSortRoster` model (cycle 18) into the sidebar's
 * search row: a name search, a starred-only toggle, a live-state facet, and a
 * recent-activity/name sort — the persistent filters the row describes. Given
 * a roster array it renders the filtered/sorted list; it owns only view state.
 *
 * Deferred (needs backend): the roster DATA itself (the crew→member mapping,
 * per-crew star persistence, live-state from `slots`/`autonudge`) and mounting
 * this under `/members`. This is the tested building block that surface
 * composes, not the fetch.
 */
const STATE_LABEL: Record<MemberLiveState, string> = {
  working: "Working", "needs-you": "Needs you", unread: "Unread",
  patrolling: "Patrolling", idle: "Idle",
};

export function MembersRoster({ members, selectedId, onSelect }: {
  members: readonly RosterMember[];
  selectedId?: string;
  onSelect?: (id: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [starredOnly, setStarredOnly] = useState(false);
  const [state, setState] = useState<MemberLiveState | "all">("all");
  const [sort, setSort] = useState<RosterSort>("recent-activity");

  const visible = useMemo(
    () => filterAndSortRoster(members, {
      search, starredOnly, sort,
      states: state === "all" ? undefined : [state],
    }),
    [members, search, starredOnly, sort, state],
  );

  return (
    <div className="flex h-full flex-col gap-2" aria-label="Crew members roster">
      <div className="flex flex-wrap items-center gap-1.5">
        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search members…" aria-label="Search members"
          className="min-w-0 flex-1 rounded-md border border-border/60 bg-background/60 px-2.5 py-1 text-xs" />
        <button type="button" aria-pressed={starredOnly} aria-label="Starred only"
          onClick={() => setStarredOnly((v) => !v)}
          className={cn("rounded-md border border-border/60 px-2 py-1", starredOnly ? "text-amber-400" : "text-muted-foreground")}>
          <Star className="h-3.5 w-3.5" />
        </button>
        <select value={state} onChange={(e) => setState(e.target.value as MemberLiveState | "all")}
          aria-label="Filter by live state"
          className="rounded-md border border-border/60 bg-background/60 px-1.5 py-1 text-xs">
          <option value="all">All states</option>
          {ALL_LIVE_STATES.map((s) => <option key={s} value={s}>{STATE_LABEL[s]}</option>)}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as RosterSort)}
          aria-label="Sort roster"
          className="rounded-md border border-border/60 bg-background/60 px-1.5 py-1 text-xs">
          <option value="recent-activity">Recent activity</option>
          <option value="name">Name</option>
        </select>
      </div>
      {visible.length === 0 ? (
        <p className="text-sm italic text-muted-foreground/70">No members match.</p>
      ) : (
        <ul aria-label="Members" className="flex min-h-0 flex-1 flex-col gap-1 overflow-auto">
          {visible.map((m) => (
            <li key={m.id}>
              <button type="button" onClick={() => onSelect?.(m.id)}
                aria-current={m.id === selectedId ? "true" : undefined}
                className={cn("flex w-full items-center gap-2 rounded-md border px-2 py-1 text-left text-sm",
                  m.id === selectedId ? "border-violet-500/50 bg-violet-500/10" : "border-border/40 hover:bg-muted/40")}>
                {m.starred && <Star className="h-3 w-3 shrink-0 text-amber-400" />}
                <span className="min-w-0 flex-1 truncate">{m.name}</span>
                <span className="shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">{STATE_LABEL[m.state]}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
