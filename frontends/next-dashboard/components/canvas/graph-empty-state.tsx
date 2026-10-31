"use client";

import { motion } from "framer-motion";
import { Network, RefreshCw } from "lucide-react";

interface EmptyGraphProps {
  loading: boolean;
  hasLoaded: boolean;
  focusedRunId: string | null;
  onReload: () => void;
}

export function EmptyGraph({ loading, hasLoaded, focusedRunId, onReload }: EmptyGraphProps) {
  const title = loading || !hasLoaded
    ? "Loading graph topology…"
    : focusedRunId
      ? "No attributable topology for this workflow run."
      : "The broad graph returned no entities.";
  const detail = focusedRunId
    ? `Run ${focusedRunId} has no projected nodes or relationships.`
    : "Telemetry documents are excluded by default; broaden or change the search when entities exist.";

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-500/10"><Network className="h-6 w-6 text-violet-500/50" /></div>
      <p className="text-sm text-muted-foreground">{title}</p>
      {!loading && hasLoaded && <p className="max-w-md break-words font-mono text-[10px] text-muted-foreground/60">{detail}</p>}
      {!loading && hasLoaded && (
        <button onClick={onReload} className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-400 transition-colors hover:bg-violet-500/20">
          <RefreshCw className="h-3 w-3" /> Reload topology
        </button>
      )}
    </motion.div>
  );
}
