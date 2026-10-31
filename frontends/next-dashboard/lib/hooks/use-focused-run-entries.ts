"use client";

import { useMemo } from "react";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";
import { useTimelineData } from "@/lib/hooks/use-timeline-data";
import type { TimelineEntry } from "@/lib/types";

function mergeEntries(live: TimelineEntry[], history: TimelineEntry[]): TimelineEntry[] {
  const liveIds = new Set(live.map((entry) => entry.id));
  return [...live, ...history.filter((entry) => !liveIds.has(entry.id))];
}

export function useFocusedRunEntries(runId: string | null) {
  const history = useTimelineData(runId, runId !== null);
  const { entries: retainedLive } = useLiveToolStream();
  const live = useMemo(
    () => runId
      ? retainedLive.filter((entry) => entry.workflow_run_id === runId)
      : [],
    [retainedLive, runId],
  );
  const durable = useMemo(
    () => runId
      ? history.entries.filter((entry) => entry.workflow_run_id === runId)
      : [],
    [history.entries, runId],
  );
  const entries = useMemo(() => mergeEntries(live, durable), [live, durable]);

  return {
    entries,
    loading: history.loading,
    error: history.error,
    available: history.available,
  };
}
