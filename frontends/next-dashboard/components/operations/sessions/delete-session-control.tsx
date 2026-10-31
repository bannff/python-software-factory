"use client";

import { Trash2 } from "lucide-react";

/**
 * Arm-then-confirm delete control for the session detail's action row.
 * Split out of ``session-detail.tsx`` to keep that file under the 200 LOC
 * ceiling. A hard delete is permanent (unlike archive/reopen), so this adds
 * one extra click of friction rather than firing on the first click, matching
 * the destructive-action caution used elsewhere in this app.
 */
export function DeleteSessionControl({ confirming, busy, onArm, onConfirm, onCancel }: {
  confirming: boolean;
  busy: boolean;
  onArm: () => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!confirming) {
    return (
      <button type="button" onClick={onArm} aria-label="Delete session"
        className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs text-muted-foreground hover:border-destructive/40 hover:text-destructive">
        <Trash2 className="h-3.5 w-3.5" /> Delete
      </button>
    );
  }
  return (
    <>
      <span className="text-xs text-destructive">Delete permanently?</span>
      <button type="button" disabled={busy} onClick={onConfirm}
        className="inline-flex items-center gap-1.5 rounded-lg bg-destructive px-3 py-1.5 text-xs font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50">
        <Trash2 className="h-3.5 w-3.5" /> {busy ? "Deleting…" : "Confirm delete"}
      </button>
      <button type="button" disabled={busy} onClick={onCancel}
        className="rounded-lg border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50">
        Cancel
      </button>
    </>
  );
}
