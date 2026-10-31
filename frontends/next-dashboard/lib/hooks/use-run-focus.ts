"use client";

import { useCallback, useEffect, useState } from "react";

const RUN_QUERY_KEY = "run";

function runFromLocation(): string | null {
  if (typeof window === "undefined") return null;
  const value = new URL(window.location.href).searchParams.get(RUN_QUERY_KEY);
  return value?.trim() || null;
}

export function useRunFocus() {
  const [focusedRunId, setFocusedRunId] = useState<string | null>(runFromLocation);

  useEffect(() => {
    const sync = () => setFocusedRunId(runFromLocation());
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const update = useCallback((runId: string | null) => {
    const normalized = runId?.trim() || null;
    const url = new URL(window.location.href);
    if (normalized) url.searchParams.set(RUN_QUERY_KEY, normalized);
    else url.searchParams.delete(RUN_QUERY_KEY);
    window.history.pushState(window.history.state, "", url);
    setFocusedRunId(normalized);
  }, []);

  const focusRun = useCallback((runId: string) => update(runId), [update]);
  const clearRunFocus = useCallback(() => update(null), [update]);

  return { focusedRunId, focusRun, clearRunFocus };
}
