"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { callTool } from "@/lib/api";
import { useHealth } from "@/lib/hooks/use-health";
import { unwrapToolData } from "@/lib/tool-result-data";
import type { TimelineEntry } from "@/lib/types";
import { mapTimelineHistoryRows } from "@/lib/timeline-history";

interface TimelineDataResult {
  entries: TimelineEntry[];
  loading: boolean;
  error: string | null;
  available: boolean;
  reason: string | null;
  refresh: () => void;
}

export function useTimelineData(
  focusedRunId: string | null = null,
  enabled = true,
): TimelineDataResult {
  const { timeline } = useHealth();
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);
  const broadAvailable = timeline?.history.available ?? true;
  const shouldFetch = enabled && (focusedRunId !== null || broadAvailable);

  const fetch = useCallback(async () => {
    const request = ++requestRef.current;
    if (!shouldFetch) {
      setEntries([]);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const tool = focusedRunId
        ? "graph_get_tool_invocations_for_run"
        : "graph_list_recent_tool_invocations";
      const args = focusedRunId ? { run_id: focusedRunId, limit: 100 } : { limit: 100 };
      const data = unwrapToolData(await callTool(tool, args)) as Record<string, unknown>;
      const rows = Array.isArray(data?.rows) ? data.rows as Record<string, unknown>[] : [];
      if (request === requestRef.current) setEntries(mapTimelineHistoryRows(rows));
    } catch (err) {
      if (request === requestRef.current) {
        setEntries([]);
        setError(err instanceof Error ? err.message : "Failed to load timeline data");
      }
    } finally {
      if (request === requestRef.current) setLoading(false);
    }
  }, [focusedRunId, shouldFetch]);

  useEffect(() => {
    void fetch();
    return () => { requestRef.current += 1; };
  }, [fetch]);

  return {
    entries, loading, error,
    available: focusedRunId ? error === null : broadAvailable,
    reason: focusedRunId ? error : timeline?.history.reason ?? null,
    refresh: () => { void fetch(); },
  };
}
