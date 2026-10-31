"use client";

import { useEffect, useState } from "react";
import { CalendarClock, Loader2, Plus, RefreshCw } from "lucide-react";
import { useSchedules } from "@/lib/hooks/use-schedules";
import { ScheduleCard } from "./schedule-card";
import { ScheduleCreateDialog } from "./schedule-create";
import { ScheduleDetail } from "./schedule-detail";

/**
 * Schedules surface (M7 Operations, Option A). A responsive list/detail:
 * discoverable schedule cards on the left, a focused detail panel on the
 * right (stacked on small screens). Every lifecycle action goes through the
 * ambient-authorized ``scheduler_*`` MCP tools with revision fencing. Loading,
 * empty, error/retry, conflict-refresh, and deleted states are all truthful.
 *
 * ``focusScheduleId`` (optional) selects and focuses a schedule's detail
 * heading once — used by deep links / notification targets — then calls
 * ``onFocusHandled`` so the parent can clear the one-shot intent.
 */
export default function SchedulesView({ focusScheduleId, onFocusHandled }: {
  focusScheduleId?: string | null;
  onFocusHandled?: () => void;
} = {}) {
  const { schedules, loading, error, refresh, create, pause, resume, remove, trigger } = useSchedules();
  const [selected, setSelected] = useState<string | null>(null);
  const [wantFocus, setWantFocus] = useState(false);
  const [gone, setGone] = useState(false);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (focusScheduleId) { setSelected(focusScheduleId); setWantFocus(true); }
  }, [focusScheduleId]);

  // A previously-selected schedule that vanished (deleted elsewhere) → notice.
  useEffect(() => {
    if (selected && !loading && !schedules.some((s) => s.scheduleId === selected)) {
      setGone(true); setSelected(null);
    }
  }, [selected, schedules, loading]);

  const active = schedules.find((s) => s.scheduleId === selected) ?? null;

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="schedules-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Operations</p>
          <h1 id="schedules-title" className="mt-1 text-2xl font-semibold tracking-tight">Schedules</h1>
          <p className="mt-1 text-sm text-muted-foreground">Recurring and one-off jobs Companion X runs for you.</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={refresh} aria-label="Refresh schedules"
            className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button type="button" onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 rounded-lg bg-violet-500 px-3 py-2 text-xs font-medium text-white">
            <Plus className="h-3.5 w-3.5" /> New schedule
          </button>
        </div>
      </header>

      {creating && <ScheduleCreateDialog onClose={() => setCreating(false)} onCreate={create} />}

      {gone && (
        <div role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
          That schedule no longer exists — it may have finished or been deleted.
          <button type="button" onClick={() => setGone(false)} className="ml-2 underline hover:no-underline">Dismiss</button>
        </div>
      )}

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Schedules unavailable: {error}</span>
          <button type="button" onClick={refresh} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && schedules.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading schedules…
        </div>
      )}

      {!loading && !error && schedules.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 p-10 text-center">
          <CalendarClock className="h-8 w-8 text-violet-400/70" />
          <h2 className="mt-3 font-medium">No schedules yet</h2>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            Create one below, or ask Companion X to run something on a schedule — daily, hourly, or once at a set time.
          </p>
          <button type="button" onClick={() => setCreating(true)}
            className="mt-4 flex items-center gap-1.5 rounded-lg bg-violet-500 px-3 py-2 text-xs font-medium text-white">
            <Plus className="h-3.5 w-3.5" /> New schedule
          </button>
        </div>
      )}

      {!error && schedules.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,1.35fr)]">
          <ul className="grid content-start gap-3" aria-label="Schedules">
            {schedules.map((schedule) => (
              <li key={schedule.scheduleId}>
                <ScheduleCard
                  schedule={schedule}
                  selected={schedule.scheduleId === selected}
                  onOpen={() => { setSelected(schedule.scheduleId); setGone(false); }}
                />
              </li>
            ))}
          </ul>
          {active ? (
            <ScheduleDetail
              key={active.scheduleId}
              schedule={active}
              focusOnMount={wantFocus}
              onFocusHandled={() => { setWantFocus(false); onFocusHandled?.(); }}
              onClose={() => setSelected(null)}
              actions={{ pause, resume, remove, trigger }}
            />
          ) : (
            <div className="hidden items-center justify-center rounded-xl border border-dashed border-border/50 p-8 text-center text-sm text-muted-foreground lg:flex">
              Select a schedule to see its detail and controls.
            </div>
          )}
        </div>
      )}
    </section>
  );
}
