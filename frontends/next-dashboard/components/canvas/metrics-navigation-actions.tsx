"use client";

import { ArrowLeft, Network } from "lucide-react";
import { useWorkbenchContext } from "@/lib/workbench-context";

/** Canonical cross-surface actions for the Metrics destination. */
export function MetricsNavigationActions() {
  const {
    navigationRef,
    navigationStatus,
    canReturn,
    returnDisabledReason,
    canOpenRelatedGraph,
    relatedGraphDisabledReason,
    returnFromMetrics,
    openRelatedGraph,
  } = useWorkbenchContext();
  const returnLabel = navigationRef
    ? `Return to ${navigationRef.label}`
    : "Return to originating surface";

  return (
    <section
      aria-labelledby="metrics-navigation-heading"
      className="border-b border-border/50 bg-card/10 px-4 py-3"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2
          id="metrics-navigation-heading"
          className="text-xs font-semibold text-foreground/90"
        >
          Navigation
        </h2>
        <p role="status" aria-live="polite" className="text-[10px] text-muted-foreground">
          {navigationStatus}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => returnFromMetrics()}
          disabled={!canReturn}
          aria-describedby="metrics-return-help"
          title={!canReturn ? returnDisabledReason : returnLabel}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/50 px-2.5 py-1.5 text-xs text-foreground/80 transition-colors hover:bg-accent/30 disabled:cursor-not-allowed disabled:opacity-45"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          {returnLabel}
        </button>
        <button
          type="button"
          onClick={() => openRelatedGraph()}
          disabled={!canOpenRelatedGraph}
          aria-describedby="metrics-graph-help"
          title={!canOpenRelatedGraph ? relatedGraphDisabledReason : "Open related graph"}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/50 px-2.5 py-1.5 text-xs text-foreground/80 transition-colors hover:bg-accent/30 disabled:cursor-not-allowed disabled:opacity-45"
        >
          <Network className="h-3.5 w-3.5" aria-hidden="true" />
          Open related graph
        </button>
      </div>
      <div className="mt-2 space-y-0.5 text-[10px] text-muted-foreground" aria-live="polite">
        {!canReturn && <p id="metrics-return-help">{returnDisabledReason}</p>}
        {!canOpenRelatedGraph && <p id="metrics-graph-help">{relatedGraphDisabledReason}</p>}
      </div>
    </section>
  );
}
