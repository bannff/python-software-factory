"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { X } from "lucide-react";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";
import { useTimelineData } from "@/lib/hooks/use-timeline-data";
import { useTimelineFocus } from "@/lib/hooks/use-timeline-focus";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { matchesSearch, sortEntries, type SortMode } from "@/lib/timeline-filters";
import type { TimelineEntry } from "@/lib/types";
import { EntityChip } from "./entity-chip";
import { TimelineControlRail } from "./timeline-control-rail";
import { TimelineEmptyState, TimelineLoadingState, type TimelineFilterId } from "./timeline-view-v2-chrome";
import { TimelineFocusedRun } from "./timeline-focused-run";
import { TimelineSpineSection } from "./timeline-spine-section";

interface ChipFilter { kind: "brick" | "session"; value: string }
function normalizeTs(timestamp: number): number { return timestamp < 1e12 ? timestamp * 1000 : timestamp; }

export function TimelineViewV2Live() {
  const workbench = useWorkbenchContext();
  if (workbench.focusedRunId) {
    return <TimelineFocusedRun runId={workbench.focusedRunId} onClear={workbench.clearRunFocus} />;
  }
  return <BroadTimeline onFocusRun={workbench.focusRun} />;
}

function BroadTimeline({ onFocusRun }: { onFocusRun: (runId: string) => void }) {
  const { entries: history, loading, available } = useTimelineData();
  const { entries: live, connected } = useLiveToolStream();
  const { selection, clearSelection } = useTimelineFocus();
  const focusSelection = selection?.key.startsWith("run:") ? null : selection;
  const [activeFilter, setActiveFilter] = useState<TimelineFilterId>("all");
  const [chipFilter, setChipFilter] = useState<ChipFilter | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const seenIds = useRef(new Set<string>());

  const newIds = useMemo(() => {
    const fresh = new Set<string>();
    for (const entry of live) if (!seenIds.current.has(entry.id)) fresh.add(entry.id);
    fresh.forEach((id) => seenIds.current.add(id));
    return fresh;
  }, [live]);
  const allEntries = useMemo(() => {
    const liveIds = new Set(live.map((entry) => entry.id));
    return [...live, ...history.filter((entry) => !liveIds.has(entry.id))];
  }, [live, history]);
  const filtered = useMemo(() => {
    let rows = allEntries;
    if (chipFilter?.kind === "brick") rows = rows.filter((entry) => entry.detail === chipFilter.value);
    if (chipFilter?.kind === "session") rows = rows.filter((entry) => entry.session_id === chipFilter.value);
    if (focusSelection?.entryIds.length) {
      const ids = new Set(focusSelection.entryIds);
      rows = rows.filter((entry) => ids.has(entry.id));
    }
    if (searchQuery) rows = rows.filter((entry) => matchesSearch(entry, searchQuery));
    if (activeFilter === "failed") rows = rows.filter((entry) => entry.status === "failed");
    if (activeFilter === "recent") rows = rows.filter((entry) => normalizeTs(entry.timestamp) >= Date.now() - 3_600_000);
    return sortEntries(rows, sortMode);
  }, [allEntries, chipFilter, focusSelection, searchQuery, activeFilter, sortMode]);
  const buckets = useMemo(() => {
    const result: Record<"now" | "lastHour" | "earlier", TimelineEntry[]> = { now: [], lastHour: [], earlier: [] };
    for (const entry of filtered) {
      const age = Date.now() - normalizeTs(entry.timestamp);
      result[age <= 60_000 ? "now" : age <= 3_600_000 ? "lastHour" : "earlier"].push(entry);
    }
    return result;
  }, [filtered]);
  const failedCount = useMemo(() => live.filter((entry) => entry.status === "failed").length, [live]);
  const filterBrick = useCallback((value: string) => setChipFilter((current) => current?.kind === "brick" && current.value === value ? null : { kind: "brick", value }), []);
  const filterSession = useCallback((value: string) => setChipFilter((current) => current?.kind === "session" && current.value === value ? null : { kind: "session", value }), []);

  return (
    <div className="flex h-full flex-col text-sm" style={{ minHeight: 0 }}>
      <TimelineControlRail liveCount={live.length} historicalCount={history.length} failedCount={failedCount} connected={connected} searchQuery={searchQuery} onSearchChange={setSearchQuery} sortMode={sortMode} onSortChange={setSortMode} activeFilter={activeFilter} onFilterChange={setActiveFilter} />
      <div className="flex-1 overflow-auto" style={{ minHeight: 0 }}>
        <div className="mx-auto max-w-[660px] px-4 py-5">
          {chipFilter && (
            <div className="mb-4 flex items-center gap-2">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-border/40 bg-card/40 px-2.5 py-1">
                <EntityChip kind={chipFilter.kind} value={chipFilter.value} />
                <button onClick={() => setChipFilter(null)} aria-label="Clear filter" className="rounded-full p-0.5 text-muted-foreground hover:bg-accent/30 hover:text-foreground"><X className="h-3 w-3" /></button>
              </div>
              <span className="text-[10px] text-muted-foreground">{filtered.length} matching</span>
            </div>
          )}
          {focusSelection && (
            <div className="mb-4 flex items-center gap-3 rounded-lg border border-sky-500/20 bg-sky-500/[0.06] px-3 py-2">
              <div className="min-w-0 flex-1"><p className="text-xs font-semibold text-sky-200">Focused: {focusSelection.title}</p><p className="text-[10px] text-muted-foreground">{focusSelection.subtitle}</p></div>
              <button onClick={clearSelection} aria-label="Clear focus" className="inline-flex items-center gap-1 rounded-md border border-border/40 px-2 py-1 text-[10px] text-muted-foreground hover:bg-accent/20 hover:text-foreground">Clear <X className="h-3 w-3" /></button>
            </div>
          )}
          {buckets.now.length > 0 && <TimelineSpineSection label="NOW" dot entries={buckets.now} newIds={newIds} onFilterBrick={filterBrick} onFilterRun={onFocusRun} onFilterSession={filterSession} />}
          {buckets.lastHour.length > 0 && <TimelineSpineSection label="LAST HOUR" entries={buckets.lastHour} newIds={newIds} onFilterBrick={filterBrick} onFilterRun={onFocusRun} onFilterSession={filterSession} />}
          {buckets.earlier.length > 0 && <TimelineSpineSection label="EARLIER" entries={buckets.earlier} newIds={newIds} onFilterBrick={filterBrick} onFilterRun={onFocusRun} onFilterSession={filterSession} />}
          {!loading && filtered.length === 0 && <TimelineEmptyState filter={activeFilter} historyAvailable={available} focusTitle={focusSelection?.title} />}
          {loading && history.length === 0 && <TimelineLoadingState />}
        </div>
      </div>
    </div>
  );
}
