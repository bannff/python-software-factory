"use client";

import { X } from "lucide-react";

export function FocusedRunBanner({
  runId,
  onClear,
  label = "Focused workflow run",
}: {
  runId: string;
  onClear: () => void;
  label?: string;
}) {
  return (
    <div className="flex items-center gap-3 border-b border-sky-500/20 bg-sky-500/[0.06] px-4 py-2">
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-medium uppercase tracking-wider text-sky-300/80">{label}</p>
        <p className="truncate font-mono text-xs text-sky-100" title={runId}>{runId}</p>
      </div>
      <button
        onClick={onClear}
        className="inline-flex items-center gap-1 rounded-md border border-border/40 px-2 py-1 text-[10px] text-muted-foreground transition-colors hover:bg-accent/20 hover:text-foreground"
        aria-label="Clear focused run"
      >
        Clear <X className="h-3 w-3" />
      </button>
    </div>
  );
}
