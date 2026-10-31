"use client";

import { AlertCircle, GitBranch } from "lucide-react";
import { useFocusedRunEntries } from "@/lib/hooks/use-focused-run-entries";
import { FocusedRunBanner } from "./focused-run-banner";
import { TimelineLoadingState } from "./timeline-view-v2-chrome";
import { TimelineRunTrace } from "./timeline-run-trace";

export function TimelineFocusedRun({ runId, onClear }: { runId: string; onClear: () => void }) {
  const focused = useFocusedRunEntries(runId);

  return (
    <div className="flex h-full flex-col text-sm" style={{ minHeight: 0 }}>
      <FocusedRunBanner runId={runId} onClear={onClear} label="Exact attributed timeline" />
      {focused.loading ? <TimelineLoadingState /> : focused.error || !focused.available ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
          <AlertCircle className="h-5 w-5 text-amber-400/70" />
          <p className="text-sm text-foreground/80">Timeline unavailable for this run.</p>
          <p className="max-w-md text-xs text-muted-foreground">{focused.error ?? "The exact run history API is unavailable."}</p>
        </div>
      ) : focused.entries.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
          <GitBranch className="h-6 w-6 text-muted-foreground/30" />
          <p className="text-sm text-foreground/80">No attributed invocations for this run.</p>
          <p className="max-w-md text-xs text-muted-foreground">The exact run query succeeded and returned no durable or retained live rows.</p>
        </div>
      ) : (
        <div className="min-h-0 flex-1"><TimelineRunTrace entries={focused.entries} runId={runId} onBack={onClear} /></div>
      )}
    </div>
  );
}
