"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Row 28 (feature-map) — Back / Forward over the workbench's view history.
 * Pure and presentational: each arrow disables when there is nowhere to go.
 * Scaffold: the draft-guard before an unarmed pop and keyboard shortcuts
 * (⌘←/⌘→) are deferred.
 */
export function NavHistoryArrows({ canBack, canForward, onBack, onForward }: {
  canBack: boolean;
  canForward: boolean;
  onBack: () => void;
  onForward: () => void;
}) {
  const base = "flex h-9 w-8 items-center justify-center border-b border-border/50 text-muted-foreground transition-colors";
  return (
    <div className="flex shrink-0">
      <button type="button" aria-label="Back" title="Back" disabled={!canBack} onClick={onBack}
        className={cn(base, canBack ? "hover:text-foreground hover:bg-card/20" : "opacity-30")}>
        <ChevronLeft className="h-4 w-4" />
      </button>
      <button type="button" aria-label="Forward" title="Forward" disabled={!canForward} onClick={onForward}
        className={cn(base, canForward ? "hover:text-foreground hover:bg-card/20" : "opacity-30")}>
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}
