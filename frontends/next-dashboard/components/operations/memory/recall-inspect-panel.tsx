"use client";

import { useEffect, useState } from "react";
import { GitBranch, Loader2, X } from "lucide-react";
import { callTool } from "@/lib/api";
import { parseRecallPath, type RecallPath } from "./recall-path-types";

/**
 * Row 45's recall inspection (owner direction 2026-09-16): "show the graph
 * path that surfaced a memory" — the real owner/FOLLOWED_BY/similar_to
 * edges around one memory, from ``memory_recall_inspect``. Opens on-demand
 * per row so the default list stays a fast, single round-trip browse.
 */
export default function RecallInspectPanel({ memoryId, onClose }: {
  memoryId: string; onClose: () => void;
}) {
  const [path, setPath] = useState<RecallPath | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(false);
    callTool("memory_recall_inspect", { memory_id: memoryId })
      .then((raw) => { if (live) setPath(parseRecallPath(raw)); })
      .catch(() => { if (live) setError(true); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [memoryId]);

  return (
    <div role="dialog" aria-label="Recall inspection" className="mt-2 rounded-lg border border-violet-400/25 bg-violet-500/5 p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium text-violet-300">
          <GitBranch className="h-3.5 w-3.5" /> Why this surfaced
        </span>
        <button type="button" onClick={onClose} aria-label="Close recall inspection" className="rounded-md p-1 text-muted-foreground hover:bg-muted/50">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {loading && (
        <p className="mt-2 flex items-center gap-2 text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Inspecting…</p>
      )}
      {!loading && error && (
        <p className="mt-2 text-muted-foreground">Recall inspection unavailable right now.</p>
      )}
      {!loading && !error && path && !path.supported && (
        <p className="mt-2 text-muted-foreground">This memory backend has no graph to inspect.</p>
      )}
      {!loading && !error && path && path.supported && (
        <div className="mt-2 flex flex-col gap-2 text-muted-foreground">
          <p>Owner: <span className="text-foreground">{path.ownerId ?? "unknown"}</span></p>
          <p>
            Followed:{" "}
            {path.followed
              ? <span className="text-foreground">“{path.followed.content}”</span>
              : "nothing before this"}
          </p>
          <div>
            <p>Similar memories:</p>
            {path.similar.length === 0 && <p className="ml-3 italic">none linked</p>}
            <ul className="ml-3 flex flex-col gap-1">
              {path.similar.map((item) => (
                <li key={item.memory.id} className="text-foreground">
                  “{item.memory.content}”
                  {item.score !== null && <span className="text-muted-foreground"> · {item.score.toFixed(2)}</span>}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
