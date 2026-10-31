"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import * as Collapsible from "@radix-ui/react-collapsible";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { TimelineDetailPanel } from "./timeline-detail-panel";
import { EntityChip } from "./entity-chip";
import type { TimelineEntry } from "@/lib/types";

export interface TimelineBubbleRowProps {
  entry: TimelineEntry;
  isNew?: boolean;
  isLast?: boolean;
  isFirst?: boolean;
  onFilterBrick?: (brick: string) => void;
  onFilterRun?: (runId: string) => void;
  onFilterSession?: (sessionId: string) => void;
}

export function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
  return `${Math.round(ms)}ms`;
}

function relativeTime(ts: number): string {
  const ms = ts < 1e12 ? ts * 1000 : ts;
  const diff = Date.now() - ms;
  if (diff < 60_000) return `${Math.round(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
  return `${Math.round(diff / 86_400_000)}d ago`;
}

const NODE_RING: Record<string, string> = {
  completed: "border-emerald-500",
  failed: "border-red-500",
  running: "border-amber-400",
};

export function TimelineBubbleRow({
  entry,
  isNew = false,
  isLast = false,
  isFirst = false,
  onFilterBrick,
  onFilterRun,
  onFilterSession,
}: TimelineBubbleRowProps) {
  const [open, setOpen] = useState(false);
  const ringColor = NODE_RING[entry.status] ?? "border-gray-500";

  const trigger = (
    <div className="flex items-stretch gap-0">
      {/* Spine column: continuous line with ring node */}
      <div className="relative flex w-[34px] shrink-0 flex-col items-center">
        {/* Line ABOVE node */}
        {!isFirst && (
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1.5px] bg-border/50 h-[18px]" />
        )}
        {/* Ring node: white center, colored border */}
        <div
          className={cn(
            "relative z-10 mt-[14px] h-[10px] w-[10px] rounded-full",
            "border-[2.5px] bg-background",
            ringColor,
          )}
        />
        {/* Line BELOW node */}
        {!isLast && (
          <div className="absolute top-[26px] bottom-0 left-1/2 -translate-x-1/2 w-[1.5px] bg-border/50" />
        )}
      </div>

      {/* Bubble card */}
      <div
        className={cn(
          "flex-1 min-w-0 rounded-xl border border-border/40 px-3 py-2 my-[3px]",
          "transition-all duration-150",
          "hover:shadow-sm hover:border-border/70",
          open && "border-sky-500/40 bg-sky-500/[0.03]",
          entry.status === "failed" && !open && "border-red-500/20 bg-red-500/[0.02]",
        )}
        style={{ willChange: open ? "border-color" : undefined }}
      >
        {/* Row header: chevron + title + meta cluster, all siblings (no button nesting) */}
        <div className="flex items-center gap-2">
          <Collapsible.Trigger asChild>
            <button
              className={cn(
                "flex items-center gap-1.5 min-w-0 flex-1",
                "bg-transparent border-none p-0 text-left cursor-pointer",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 rounded",
              )}
              aria-label={`Toggle details for ${entry.title}`}
            >
              <ChevronRight
                className={cn(
                  "h-3 w-3 shrink-0 text-muted-foreground/60 transition-transform duration-150",
                  open && "rotate-90",
                )}
                aria-hidden="true"
              />
              <span className="truncate font-mono text-xs font-medium text-foreground/90">
                {entry.title}
              </span>
            </button>
          </Collapsible.Trigger>
          {/* Meta cluster: chips + latency + time — siblings, not inside trigger */}
          <div className="flex items-center gap-1.5 shrink-0">
            {entry.detail && (
              <EntityChip
                kind="brick"
                value={entry.detail}
                onClick={onFilterBrick ? (e) => { e.stopPropagation(); onFilterBrick(entry.detail!); } : undefined}
              />
            )}
            {entry.workflow_run_id && (
              <EntityChip
                kind="run"
                value={entry.workflow_run_id.slice(0, 8)}
                onClick={onFilterRun ? (e) => { e.stopPropagation(); onFilterRun(entry.workflow_run_id!); } : undefined}
              />
            )}
            {entry.session_id && (
              <EntityChip
                kind="session"
                value={entry.session_id.slice(0, 8)}
                onClick={onFilterSession ? (e) => { e.stopPropagation(); onFilterSession(entry.session_id!); } : undefined}
              />
            )}
            {entry.duration != null && (
              <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
                {formatDuration(entry.duration)}
              </span>
            )}
            <span className="text-[9px] text-muted-foreground/50 tabular-nums">
              {relativeTime(entry.timestamp)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );

  const content = (
    <Collapsible.Content className="overflow-hidden data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up">
      <div className="ml-[34px]">
        <TimelineDetailPanel entry={entry} isNew={isNew} />
      </div>
    </Collapsible.Content>
  );

  const wrapper = (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      {trigger}
      {content}
    </Collapsible.Root>
  );

  if (isNew) {
    return (
      <motion.div
        initial={{ opacity: 0, x: -6 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.15 }}
        style={{ willChange: "opacity, transform" }}
      >
        {wrapper}
      </motion.div>
    );
  }

  return wrapper;
}
