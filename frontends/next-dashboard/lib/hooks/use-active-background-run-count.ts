"use client";

import { useEffect, useRef, useState } from "react";
import { callTool } from "@/lib/api";

const POLL_MS = 15_000;
const MAX_CONSECUTIVE_FAILURES = 3;
const RUNNING_STATUSES = new Set(["running", "waiting"]);

/**
 * Polls the real Workflow-owned run registry (`workflow.list_runs`) and
 * returns the count of durable background agent attempts currently
 * running or waiting. `status` is an exact-match backend filter, so this
 * fetches unfiltered and counts client-side across both live statuses.
 * Zero on any error or before the first successful poll — never a
 * placeholder or fabricated number.
 *
 * Item 12(d) (owner smoke #2): backs off after
 * ``MAX_CONSECUTIVE_FAILURES`` in a row instead of hammering a tool that
 * has already failed repeatedly — a quiet 0 count, not a retry storm.
 */
export function useActiveBackgroundRunCount(): number {
  const [count, setCount] = useState(0);
  const failureCount = useRef(0);
  const unavailable = useRef(false);

  useEffect(() => {
    let mounted = true;
    async function poll() {
      if (unavailable.current) return;
      try {
        const result = await callTool("workflow.list_runs", {
          filter: {}, pagination: { limit: 100 },
        });
        const data = result as { runs?: Array<{ status?: string }> };
        const runs = Array.isArray(data.runs) ? data.runs : [];
        if (mounted) {
          setCount(runs.filter((run) => RUNNING_STATUSES.has(run.status ?? "")).length);
        }
        failureCount.current = 0;
      } catch {
        failureCount.current += 1;
        if (failureCount.current >= MAX_CONSECUTIVE_FAILURES) unavailable.current = true;
        if (mounted) setCount(0);
      }
    }
    void poll();
    const id = setInterval(poll, POLL_MS);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  return count;
}
