"use client";

import { GitBranch } from "lucide-react";

/**
 * Fork control for the session detail's action row (row 14, feature-map).
 * Split out for the same reason ``delete-session-control.tsx`` is split —
 * ``session-detail.tsx`` sits near the 200 LOC ceiling. Non-destructive
 * (reads the source, never mutates it), so a single click is enough —
 * no arm-then-confirm needed, unlike delete.
 */
export function ForkSessionControl({ busy, onFork }: {
  busy: boolean;
  onFork: () => void;
}) {
  return (
    <button type="button" disabled={busy} onClick={onFork} aria-label="Fork session"
      className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50">
      <GitBranch className="h-3.5 w-3.5" /> {busy ? "Forking…" : "Fork"}
    </button>
  );
}
