"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import {
  classifyLoopError, parseLoopCycle, parseLoopList,
  type Loop, type LoopCycle, type LoopErrorKind,
} from "@/components/operations/projects/project-types";

export interface ActionResult { status: "ok" | LoopErrorKind }

type LifecycleTool = "workflow.pause_loop" | "workflow.resume_loop" | "workflow.stop_loop";

export interface StartLoopSpec {
  title: string; spec: string; agentId: string;
  intervalSeconds: number; maxCycles: number;
}

export function useProjects() {
  const [loops, setLoops] = useState<Loop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const parsed = parseLoopList(await callTool("workflow.list_loops", {}));
      if (!mounted.current) return;
      setLoops(parsed);
      setError(null);
    } catch {
      if (mounted.current) setError("Projects unavailable");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => { mounted.current = false; };
  }, [refresh]);

  const start = useCallback(async (input: StartLoopSpec): Promise<ActionResult> => {
    try {
      unwrapToolData(await callTool("workflow.start_loop", {
        kind: "goal", agent_id: input.agentId, objective: input.title,
        cycle_instructions: input.spec, interval_seconds: input.intervalSeconds,
        max_cycles: input.maxCycles,
      }));
      await refresh();
      return { status: "ok" };
    } catch (err) {
      return { status: classifyLoopError(err) };
    }
  }, [refresh]);

  const runAction = useCallback(async (tool: LifecycleTool, loop: Loop): Promise<ActionResult> => {
    try {
      unwrapToolData(await callTool(tool, { loop_id: loop.loopId, expected_revision: loop.revision }));
      await refresh();
      return { status: "ok" };
    } catch (err) {
      const kind = classifyLoopError(err);
      await refresh();
      return { status: kind };
    }
  }, [refresh]);

  const pause = useCallback((l: Loop) => runAction("workflow.pause_loop", l), [runAction]);
  const resume = useCallback((l: Loop) => runAction("workflow.resume_loop", l), [runAction]);
  const stop = useCallback((l: Loop) => runAction("workflow.stop_loop", l), [runAction]);

  return { loops, loading, error, refresh, start, pause, resume, stop };
}

/** One loop's latest settled cycle detail, or null when not yet settled/unreadable. */
export async function fetchLoopCycle(loop: Loop): Promise<LoopCycle | null> {
  if (loop.lastSettledCycle < 1) return null;
  try {
    return parseLoopCycle(await callTool("workflow.get_loop_cycle", {
      loop_id: loop.loopId, cycle: loop.lastSettledCycle,
    }));
  } catch {
    return null;
  }
}
