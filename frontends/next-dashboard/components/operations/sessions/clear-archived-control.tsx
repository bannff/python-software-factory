"use client";

import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { clearArchivedSessions, countClearableSessions } from "./session-actions";

/**
 * Bulk "Delete all" for archived sessions (row 8, feature-map — the other
 * half of the per-session delete built earlier this cycle). Shown only
 * when the Archived filter is on, next to it — matches upstream's own
 * "Older Sessions" disclosure placement. Previews a real count before the
 * owner commits (upstream's ``clearable/count``), and only offers the
 * button at all when that count is genuinely non-zero — no dead button.
 */
export function ClearArchivedControl({ visible, onCleared }: {
  visible: boolean;
  onCleared: () => void;
}) {
  const [count, setCount] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!visible) { setConfirming(false); return; }
    let cancelled = false;
    void countClearableSessions().then((value) => { if (!cancelled) setCount(value); });
    return () => { cancelled = true; };
  }, [visible]);

  if (!visible || count === null || count === 0) return null;

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await clearArchivedSessions();
      setConfirming(false);
      setCount(0);
      onCleared();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t clear archived sessions.");
    } finally {
      setBusy(false);
    }
  };

  if (confirming) {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="text-destructive">Delete all {count} archived sessions?</span>
        <button type="button" disabled={busy} onClick={() => void confirm()}
          className="inline-flex items-center gap-1 rounded-md bg-destructive px-2 py-1 font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50">
          {busy ? "Deleting…" : "Confirm"}
        </button>
        <button type="button" disabled={busy} onClick={() => setConfirming(false)}
          className="rounded-md border border-border/60 px-2 py-1 hover:bg-muted/50 disabled:opacity-50">
          Cancel
        </button>
        {error && <span role="alert" className="text-destructive">{error}</span>}
      </div>
    );
  }

  return (
    <button type="button" onClick={() => setConfirming(true)}
      className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-2 text-xs text-muted-foreground hover:border-destructive/40 hover:text-destructive">
      <Trash2 className="h-3.5 w-3.5" /> Delete all ({count})
    </button>
  );
}
