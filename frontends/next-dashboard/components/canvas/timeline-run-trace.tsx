"use client";

import { useMemo } from "react";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { TimelineBubbleRow, formatDuration } from "./timeline-bubble-row";
import { EntityChip } from "./entity-chip";
import type { TimelineEntry } from "@/lib/types";

interface TimelineRunTraceProps {
  entries: TimelineEntry[];
  runId: string;
  onBack: () => void;
}

function normalizeTs(ts: number): number {
  return ts < 1e12 ? ts * 1000 : ts;
}

/**
 * Run-as-trace waterfall: displays all entries for a single workflow_run_id
 * in causal order (ascending timestamp) with a vertical connector line.
 */
export function TimelineRunTrace({ entries, runId, onBack }: TimelineRunTraceProps) {
  const sorted = useMemo(
    () => [...entries].sort((a, b) => normalizeTs(a.timestamp) - normalizeTs(b.timestamp)),
    [entries],
  );

  const spanMs = useMemo(() => {
    if (sorted.length < 2) return 0;
    return normalizeTs(sorted[sorted.length - 1].timestamp) - normalizeTs(sorted[0].timestamp);
  }, [sorted]);

  return (
    <div className="flex flex-col h-full">
      {/* Trace header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/30 shrink-0">
        <button
          onClick={onBack}
          aria-label="Back to stream view"
          className={cn(
            "inline-flex items-center gap-1 rounded px-2 py-1 text-[11px]",
            "text-muted-foreground hover:text-foreground hover:bg-accent/20 transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60",
          )}
        >
          <ArrowLeft className="h-3 w-3" />
          Stream
        </button>
        <div className="h-3 w-px bg-border/40" />
        <EntityChip kind="run" value={runId.slice(0, 8)} />
        <span className="text-[10px] text-muted-foreground tabular-nums">
          {sorted.length} events
        </span>
        {spanMs > 0 && (
          <span className="text-[10px] text-muted-foreground/60 tabular-nums">
            · {formatDuration(spanMs)} span
          </span>
        )}
      </div>

      {/* Trace waterfall */}
      <div className="flex-1 overflow-auto px-1" style={{ minHeight: 0 }}>
        <div className="border-l-2 border-sky-500/30 ml-4 mt-2">
          {sorted.map((entry, i) => (
            <TimelineBubbleRow
              key={entry.id}
              entry={entry}
              isLast={i === sorted.length - 1}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
