"use client";

import { useEffect } from "react";

export function useGraphRunFocus(
  focusedRunId: string | null,
  loadBroad: () => Promise<void>,
  loadExact: (runId: string) => Promise<void>,
  onChange?: () => void,
) {
  useEffect(() => {
    onChange?.();
    if (focusedRunId) void loadExact(focusedRunId);
    else void loadBroad();
  }, [focusedRunId, loadBroad, loadExact, onChange]);
}
