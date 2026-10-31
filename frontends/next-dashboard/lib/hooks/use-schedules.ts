"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import {
  classifyScheduleError,
  parseLastFire,
  parseScheduleList,
  parseScheduleOutput,
  type LastFire,
  type Schedule,
  type ScheduleCreateInput,
  type ScheduleErrorKind,
} from "@/components/operations/schedules/schedule-types";

/**
 * Owner-scoped Schedules state, backed by the real ``scheduler_*`` MCP tools.
 *
 * Identity is ambient on the backend — no tenant/owner/envelope is ever sent.
 * Every lifecycle action is fenced by the record's ``revision``; a CAS
 * conflict or a vanished (deleted) schedule refreshes the truth and reports
 * the classification rather than fabricating success. Failures degrade to a
 * truthful error string so the view can render retry, never a fake empty.
 */
export interface ActionResult {
  status: "ok" | ScheduleErrorKind;
}

type LifecycleTool = "scheduler_pause" | "scheduler_resume" | "scheduler_remove" | "scheduler_trigger";

export function useSchedules() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const parsed = parseScheduleList(await callTool("scheduler_list", {}));
      if (!mounted.current) return;
      setSchedules(parsed);
      setError(null);
    } catch {
      if (mounted.current) setError("Schedules unavailable");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  const runAction = useCallback(
    async (tool: LifecycleTool, schedule: Schedule): Promise<ActionResult> => {
      try {
        const raw = await callTool(tool, {
          schedule_id: schedule.scheduleId,
          expected_revision: schedule.revision,
        });
        // callTool resolves even on a domain ok:false envelope — unwrap so a
        // revision conflict / not-found becomes a throw we can classify.
        unwrapToolData(raw);
        await refresh();
        return { status: "ok" };
      } catch (err) {
        const kind = classifyScheduleError(err);
        // Conflict or deleted → the list is now stale; refresh to the truth.
        await refresh();
        return { status: kind };
      }
    },
    [refresh],
  );

  const pause = useCallback((s: Schedule) => runAction("scheduler_pause", s), [runAction]);
  const resume = useCallback((s: Schedule) => runAction("scheduler_resume", s), [runAction]);
  const remove = useCallback((s: Schedule) => runAction("scheduler_remove", s), [runAction]);
  const trigger = useCallback((s: Schedule) => runAction("scheduler_trigger", s), [runAction]);

  const create = useCallback(async (input: ScheduleCreateInput): Promise<ActionResult> => {
    try {
      parseScheduleOutput(await callTool("scheduler_add", {
        agent_id: input.agentId, task: input.task, kind: input.kind,
        interval_seconds: input.intervalSeconds ?? null,
        one_shot_at: input.oneShotAt ?? null,
        cron_expression: input.cronExpression ?? null,
        timezone_name: input.timezoneName || "UTC",
      }));
      await refresh();
      return { status: "ok" };
    } catch (err) {
      return { status: classifyScheduleError(err) };
    }
  }, [refresh]);

  return { schedules, loading, error, refresh, create, pause, resume, remove, trigger };
}

/**
 * Read the last fire's plain-language outcome for one schedule. Returns null
 * when the schedule has never fired or the fire record is unreadable — the
 * detail view falls back to the record-only summary rather than a raw code.
 */
export async function fetchLastFire(schedule: Schedule): Promise<LastFire | null> {
  if (schedule.fireSequence < 1) return null;
  try {
    return parseLastFire(
      await callTool("scheduler_get_fire", {
        schedule_id: schedule.scheduleId,
        fire_sequence: schedule.fireSequence,
      }),
    );
  } catch {
    return null;
  }
}
