"use client";

import { CalendarClock } from "lucide-react";
import type { Schedule } from "./schedule-types";
import {
  describeShape, listOutcome, nextFireLabel, STATE_LABEL, STATE_TONE,
} from "./schedule-presenters";

/**
 * One schedule as a discoverable card/list row. Shows the state at a glance,
 * the schedule shape, the next fire, and a coarse last-outcome hint — all in
 * plain language, so a first-time user understands it without opening detail.
 */
export function ScheduleCard({ schedule, selected, onOpen }: {
  schedule: Schedule; selected: boolean; onOpen: () => void;
}) {
  const outcome = listOutcome(schedule);
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Open schedule ${schedule.scheduleId}`}
      aria-current={selected ? "true" : undefined}
      className={`group flex w-full min-w-0 flex-col gap-2 rounded-xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:border-violet-500/40 hover:bg-card/60 ${
        selected ? "border-violet-500/50 bg-card/60" : "border-border/60 bg-card/30"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-3">
          <span className="rounded-lg bg-violet-500/10 p-2 text-violet-400">
            <CalendarClock className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h3 className="truncate font-medium" title={schedule.agentId}>{schedule.agentId}</h3>
            <p className="truncate text-xs text-muted-foreground">{schedule.scheduleId}</p>
          </div>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium ${STATE_TONE[schedule.state]}`}>
          {STATE_LABEL[schedule.state]}
        </span>
      </div>
      <p className="line-clamp-2 min-h-8 text-sm text-muted-foreground">{schedule.task}</p>
      <dl className="grid min-w-0 gap-1 border-t border-border/40 pt-2 text-xs">
        <div className="flex min-w-0 items-center gap-2">
          <dt className="shrink-0 text-muted-foreground/60">Runs</dt>
          <dd className="m-0 min-w-0 flex-1 truncate text-foreground/90">{describeShape(schedule)}</dd>
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <dt className="shrink-0 text-muted-foreground/60">Next</dt>
          <dd className="m-0 min-w-0 flex-1 truncate text-foreground/90">{nextFireLabel(schedule)}</dd>
        </div>
        <div className="flex min-w-0 items-center gap-2">
          <dt className="shrink-0 text-muted-foreground/60">Status</dt>
          <dd className={`m-0 min-w-0 flex-1 truncate font-medium ${outcome.tone}`}>{outcome.label}</dd>
        </div>
      </dl>
    </button>
  );
}
