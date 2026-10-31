"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimelineEntry } from "@/lib/types";
import { TimelineDetailPanel } from "./timeline-detail-panel";

export interface DrilldownState {
  key: string;
  title: string;
  subtitle: string;
  entries: TimelineEntry[];
}

type DrilldownFilter = "all" | "completed" | "failed" | "running";

interface RuntimeMetricsDrilldownProps {
  drilldown: DrilldownState;
  onOpenTimeline?: (entries: TimelineEntry[], title: string, subtitle: string) => void;
}

function accentFor(entry: TimelineEntry): string {
  if (entry.status === "completed") return "border-emerald-500/50";
  if (entry.status === "failed") return "border-red-500/50";
  if (entry.status === "running") return "border-yellow-400/50";
  return "border-gray-500/50";
}

function isLiveEntry(entry: TimelineEntry): boolean {
  return entry.id.startsWith("live-");
}

function formatDuration(duration: number): string {
  if (duration < 1) return `${Math.round(duration * 1000)}μs`;
  if (duration >= 1000) return `${(duration / 1000).toFixed(1)}s`;
  return `${Math.round(duration)}ms`;
}

export function RuntimeMetricsDrilldown({ drilldown, onOpenTimeline }: RuntimeMetricsDrilldownProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<DrilldownFilter>("all");

  const counts = useMemo(() => ({
    completed: drilldown.entries.filter((entry) => entry.status === "completed").length,
    failed: drilldown.entries.filter((entry) => entry.status === "failed").length,
    running: drilldown.entries.filter((entry) => entry.status === "running").length,
  }), [drilldown.entries]);

  const filteredEntries = useMemo(() => {
    if (activeFilter === "all") return drilldown.entries;
    return drilldown.entries.filter((entry) => entry.status === activeFilter);
  }, [activeFilter, drilldown.entries]);

  const filterLabel = activeFilter === "all"
    ? `${filteredEntries.length} events`
    : `${filteredEntries.length} ${activeFilter}`;

  return (
    <motion.section
      initial={{ opacity: 0, y: -8, height: 0 }}
      animate={{ opacity: 1, y: 0, height: "auto" }}
      exit={{ opacity: 0, y: -8, height: 0 }}
      transition={{ duration: 0.16 }}
      className="overflow-hidden rounded-xl border border-sky-500/20 bg-sky-500/[0.04]"
    >
      <div className="border-b border-sky-500/15 px-4 py-3">
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold text-foreground/90">{drilldown.title}</h2>
            <p className="text-xs text-muted-foreground">{drilldown.subtitle}</p>
          </div>
          {onOpenTimeline && filteredEntries.length > 0 && (
            <button
              onClick={() => onOpenTimeline(filteredEntries, drilldown.title, drilldown.subtitle)}
              className="inline-flex items-center gap-1 rounded-md border border-border/40 px-2.5 py-1 text-[10px] font-medium text-sky-300 transition-colors hover:bg-accent/20"
            >
              Open in Timeline
              <ExternalLink className="h-3 w-3" />
            </button>
          )}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {([
            { id: "all", label: "all" },
            { id: "completed", label: `completed (${counts.completed})` },
            { id: "failed", label: `failed (${counts.failed})` },
            { id: "running", label: `running (${counts.running})` },
          ] as Array<{ id: DrilldownFilter; label: string }>).map((filter) => (
            <button
              key={filter.id}
              onClick={() => setActiveFilter(filter.id)}
              className={cn(
                "rounded-full px-2.5 py-0.5 text-[10px] font-medium transition-colors",
                activeFilter === filter.id
                  ? "bg-sky-500/15 text-sky-200 ring-1 ring-sky-400/30"
                  : "bg-background/40 text-muted-foreground hover:text-foreground hover:bg-accent/30",
              )}
            >
              {filter.label}
            </button>
          ))}
          <span className="ml-auto text-[10px] text-muted-foreground">{filterLabel}</span>
        </div>
      </div>
      <div className="max-h-[26rem] overflow-auto p-3">
        {filteredEntries.length > 0 ? (
          <div className="space-y-2">
            {filteredEntries.map((entry) => {
              const open = expandedId === entry.id;
              return (
                <div key={entry.id} className="rounded-lg border border-border/40 bg-background/30">
                  <button
                    onClick={() => setExpandedId((current) => current === entry.id ? null : entry.id)}
                    className={cn(
                      "flex w-full items-center gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-accent/20",
                      open && "bg-accent/15",
                    )}
                  >
                    <span className={cn(
                      "h-2 w-2 rounded-full shrink-0",
                      entry.status === "completed" && "bg-emerald-400",
                      entry.status === "failed" && "bg-red-400",
                      entry.status === "running" && "bg-yellow-400",
                    )} />
                    <span className="min-w-0 flex-1 truncate font-mono text-xs text-foreground/85">{entry.title}</span>
                    {entry.detail && (
                      <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-300">
                        {entry.detail}
                      </span>
                    )}
                    {entry.duration != null && (
                      <span className="text-[10px] text-muted-foreground">{formatDuration(entry.duration)}</span>
                    )}
                    <ChevronRight className={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform", open && "rotate-90")} />
                  </button>
                  <AnimatePresence initial={false}>
                    {open && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.14 }}
                        className="overflow-hidden"
                      >
                        <TimelineDetailPanel entry={entry} isNew={isLiveEntry(entry)} accentColor={accentFor(entry)} />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Nothing in the current buffer matches this filter yet.</p>
        )}
      </div>
    </motion.section>
  );
}