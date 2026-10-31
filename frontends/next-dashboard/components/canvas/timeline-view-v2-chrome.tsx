"use client";

/**
 * Section label + empty / loading states for ``TimelineViewV2Live``.
 * Extracted so the live-mode file fits the 200-LOC budget after the
 * bd-F carrier #2 dispatcher landed.
 */

import { GitBranch, RefreshCw } from "lucide-react";

export type TimelineFilterId = "all" | "recent" | "failed";

export function SectionLabel({ label, dot }: { label: string; dot?: boolean }) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-1 sticky top-0 bg-background/80 backdrop-blur-sm z-10">
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />}
      <span className="text-[9px] font-semibold tracking-widest text-muted-foreground/60 uppercase">
        {label}
      </span>
    </div>
  );
}

export function TimelineEmptyState({
  filter,
  historyAvailable,
  focusTitle,
}: {
  filter: TimelineFilterId;
  historyAvailable: boolean;
  focusTitle?: string;
}) {
  const msg = focusTitle
    ? `No retained live events currently match ${focusTitle}.`
    : !historyAvailable
    ? "Live timeline is active. Historical activity is unavailable in lightweight mode."
    : filter === "failed"
    ? "No failed tool calls found."
    : filter === "recent"
    ? "No tool calls in the last hour."
    : "No tool invocations recorded yet.";
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <GitBranch className="h-6 w-6 text-muted-foreground/30" />
      <p className="text-xs text-muted-foreground/50">{msg}</p>
    </div>
  );
}

export function TimelineLoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground/40" />
    </div>
  );
}
