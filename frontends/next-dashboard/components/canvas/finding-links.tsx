"use client";

import { GitBranch, Network, type LucideIcon } from "lucide-react";
import { useWorkbenchContext } from "@/lib/workbench-context";
import type { CanvasViewId } from "@/lib/types";

const TARGETS: { view: CanvasViewId; label: string; icon: LucideIcon }[] = [
  { view: "timeline-v2", label: "Timeline", icon: GitBranch },
  { view: "graph", label: "Graph", icon: Network },
];

/** Where this finding came from, one click away in the tabs that know the run. */
export function FindingLinks({ runId }: { runId?: string }) {
  const workbench = useWorkbenchContext();
  if (!runId) return null;
  return (
    <div className="flex items-center gap-1.5">
      {TARGETS.map(({ view, label, icon: Icon }) => (
        <button key={view} type="button" aria-label={`Open run in ${label}`} title={`Open run in ${label}`}
          onClick={() => { workbench.focusRun(runId); workbench.switchView(view); }}
          className="inline-flex items-center gap-1 rounded-md border border-border/50 px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-accent/30 hover:text-foreground">
          <Icon className="h-3 w-3" aria-hidden /> {label}
        </button>
      ))}
    </div>
  );
}
