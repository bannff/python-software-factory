"use client";

import type { Loop } from "./project-types";

const STATE_LABEL: Record<Loop["state"], string> = {
  active: "Active", paused: "Paused", stopped: "Stopped", completed: "Completed",
};
export const STATE_TONE: Record<Loop["state"], string> = {
  active: "border-emerald-500/40 text-emerald-300",
  paused: "border-amber-500/40 text-amber-300",
  stopped: "border-border/60 text-muted-foreground",
  completed: "border-violet-500/40 text-violet-300",
};

export function ProjectCard({ loop, selected, onOpen }: { loop: Loop; selected: boolean; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} aria-pressed={selected}
      className={`w-full rounded-lg border p-3 text-left transition-colors ${
        selected ? "border-violet-500/50 bg-violet-500/[0.06]" : "border-border/50 hover:bg-muted/30"
      }`}>
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 truncate text-sm font-medium">{loop.objective}</p>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${STATE_TONE[loop.state]}`}>
          {STATE_LABEL[loop.state]}
        </span>
      </div>
      <p className="mt-1 truncate text-xs text-muted-foreground">{loop.agentId} · cycle {loop.lastSettledCycle}/{loop.maxCycles || "∞"}</p>
    </button>
  );
}
