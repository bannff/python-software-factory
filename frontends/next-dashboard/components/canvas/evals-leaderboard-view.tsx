"use client";

import { useWorkbenchContext } from "@/lib/workbench-context";
import type { CanvasViewId } from "@/lib/types";
import { EvalsFocusedRun } from "./evals-focused-run";
import { EvalsLeaderboardAggregate } from "./evals-leaderboard-aggregate";

interface EvalsLeaderboardViewProps {
  onNavigate?: (viewId: CanvasViewId) => void;
}

export default function EvalsLeaderboardView({ onNavigate }: EvalsLeaderboardViewProps) {
  const workbench = useWorkbenchContext();
  if (workbench.focusedRunId) {
    return <EvalsFocusedRun runId={workbench.focusedRunId} onClear={workbench.clearRunFocus} />;
  }
  return (
    <EvalsLeaderboardAggregate
      onRunSelect={(runId) => {
        workbench.focusRun(runId);
        onNavigate?.("timeline-v2");
      }}
    />
  );
}
