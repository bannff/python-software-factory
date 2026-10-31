"use client";

import { useEffect, useState } from "react";
import { History, Loader2, X } from "lucide-react";
import { callTool } from "@/lib/api";
import { parseMemoryHistory, type MemoryHistory } from "./history-types";

/**
 * Row 47 (Replaced experiences) — the memory-detail history view the row's
 * own status names as the missing piece ("no memory detail/click-through
 * view exists anywhere in the app"). Lists every version of the chain
 * containing a memory, newest first, from ``memory_history``.
 *
 * Deliberately informational only, mirroring ``RecallInspectPanel``'s
 * shape: NO restore action is offered, because upstream's "restore one"
 * conflicts with a real owner ruling recorded in this same substrate
 * (``graph_supersession.py``: "the curator... replaces memories — never
 * a user-facing restore action"). Row 45's sibling bulk-edit/seed-copy
 * gap was ruled OWNER_DEFERRED on the exact same "curator owns this"
 * reasoning — this view applies that ruling consistently rather than
 * building a restore button the owner has already said should not exist.
 */
export default function MemoryHistoryPanel({ memoryId, onClose }: {
  memoryId: string; onClose: () => void;
}) {
  const [history, setHistory] = useState<MemoryHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(false);
    callTool("memory_history", { memory_id: memoryId })
      .then((raw) => { if (live) setHistory(parseMemoryHistory(raw)); })
      .catch(() => { if (live) setError(true); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [memoryId]);

  return (
    <div role="dialog" aria-label="Memory history" className="mt-2 rounded-lg border border-sky-400/25 bg-sky-500/5 p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium text-sky-300">
          <History className="h-3.5 w-3.5" /> Replaced experiences
        </span>
        <button type="button" onClick={onClose} aria-label="Close memory history" className="rounded-md p-1 text-muted-foreground hover:bg-muted/50">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {loading && (
        <p className="mt-2 flex items-center gap-2 text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading history…</p>
      )}
      {!loading && error && (
        <p className="mt-2 text-muted-foreground">History unavailable right now.</p>
      )}
      {!loading && !error && history && !history.supported && (
        <p className="mt-2 text-muted-foreground">This memory backend has no history to inspect.</p>
      )}
      {!loading && !error && history && history.supported && history.versions.length <= 1 && (
        <p className="mt-2 text-muted-foreground">This memory has never been replaced.</p>
      )}
      {!loading && !error && history && history.supported && history.versions.length > 1 && (
        <ul className="mt-2 flex flex-col gap-2" aria-label="Version history">
          {history.versions.map((version, index) => (
            <li key={version.id} className="rounded-md border border-border/50 bg-background/40 p-2">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className={index === 0 ? "rounded-full bg-sky-500/15 px-2 py-0.5 text-sky-300" : ""}>
                  {index === 0 ? "Current" : "Replaced"}
                </span>
                {version.createdAt && <span>{new Date(version.createdAt).toLocaleString()}</span>}
              </div>
              <p className="mt-1 text-foreground">{version.content}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
