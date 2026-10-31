"use client";

import { cn } from "@/lib/utils";
import type { TimelineEntry } from "@/lib/types";
import { TimelineBubbleRow } from "./timeline-bubble-row";

export function TimelineSpineSection({
  label, dot, entries, newIds, onFilterBrick, onFilterRun, onFilterSession,
}: {
  label: string;
  dot?: boolean;
  entries: TimelineEntry[];
  newIds: Set<string>;
  onFilterBrick: (value: string) => void;
  onFilterRun: (value: string) => void;
  onFilterSession: (value: string) => void;
}) {
  return (
    <section className="mb-5">
      <div className="mb-2 ml-[10px] flex items-center gap-2">
        <div className={cn("inline-flex items-center gap-1.5 rounded-full border border-border/30 bg-background px-2.5 py-0.5")}>
          {dot && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}
          <span className="text-[9px] font-semibold uppercase tracking-widest text-muted-foreground/70">{label}</span>
        </div>
        <div className="h-px flex-1 bg-border/20" />
      </div>
      <div>
        {entries.map((entry, index) => (
          <TimelineBubbleRow
            key={entry.id} entry={entry} isNew={newIds.has(entry.id)}
            isFirst={index === 0} isLast={index === entries.length - 1}
            onFilterBrick={onFilterBrick} onFilterRun={onFilterRun}
            onFilterSession={onFilterSession}
          />
        ))}
      </div>
    </section>
  );
}
