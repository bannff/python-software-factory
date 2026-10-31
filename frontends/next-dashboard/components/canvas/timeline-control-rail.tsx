"use client";

import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import type { SortMode } from "@/lib/timeline-filters";

interface TimelineControlRailProps {
  liveCount: number;
  historicalCount: number;
  failedCount: number;
  connected: boolean;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortMode: SortMode;
  onSortChange: (mode: SortMode) => void;
  activeFilter: "all" | "recent" | "failed";
  onFilterChange: (filter: "all" | "recent" | "failed") => void;
}

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "slowest", label: "Slowest" },
];

/**
 * Single control bar: search | sort | live pulse + counts | failed badge | filter tabs.
 */
export function TimelineControlRail({
  liveCount,
  historicalCount,
  failedCount,
  connected,
  searchQuery,
  onSearchChange,
  sortMode,
  onSortChange,
  activeFilter,
  onFilterChange,
}: TimelineControlRailProps) {
  return (
    <div className="flex flex-col gap-1.5 px-3 py-2 border-b border-border/20 shrink-0">
      {/* Row 1: Search + sort */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" aria-hidden="true" />
          <Input
            type="search"
            aria-label="Search timeline events"
            placeholder="Search tool, brick, run, session…"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="h-7 pl-7 pr-2 text-[11px] bg-background/50 border-border/30"
          />
        </div>
        <div className="flex items-center rounded border border-border/30 overflow-hidden" role="group" aria-label="Sort order">
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => onSortChange(opt.value)}
              aria-pressed={sortMode === opt.value}
              className={cn(
                "px-2 py-1 text-[10px] transition-colors",
                sortMode === opt.value
                  ? "bg-sky-500/15 text-sky-300 font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/20",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Row 2: Live stats + filter tabs */}
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
        {/* Live pulse */}
        <span className="inline-flex items-center gap-1.5">
          <span
            className={cn(
              "h-2 w-2 rounded-full shrink-0",
              connected ? "bg-emerald-400 animate-pulse" : "bg-amber-400",
            )}
            aria-hidden="true"
          />
          <span className="tabular-nums">
            <span className="text-emerald-400 font-medium">{liveCount}</span> live
          </span>
          <span className="text-foreground/30">·</span>
          <span className="tabular-nums">
            <span className="text-foreground/60">{historicalCount}</span> hist
          </span>
        </span>

        {/* Failed badge — only if >0 */}
        {failedCount > 0 && (
          <button
            onClick={() => onFilterChange("failed")}
            aria-label={`${failedCount} failed — click to filter`}
            className={cn(
              "inline-flex items-center gap-1 rounded px-1.5 py-0.5",
              "bg-red-500/10 text-red-400 text-[10px] font-medium tabular-nums",
              "hover:bg-red-500/20 transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/60",
            )}
          >
            {failedCount} failed
          </button>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Filter tabs */}
        <div className="flex items-center gap-0.5">
          {(["all", "recent", "failed"] as const).map((id) => (
            <button
              key={id}
              onClick={() => onFilterChange(id)}
              aria-label={`Filter: ${id}`}
              className={cn(
                "rounded px-2 py-0.5 text-[10px] transition-colors capitalize",
                activeFilter === id
                  ? "bg-white/8 text-foreground/80 border border-border/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/30",
              )}
            >
              {id}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
