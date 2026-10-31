"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Pause, Play, Trash2 } from "lucide-react";
import type { ActionResult } from "@/lib/hooks/use-schedules";
import { fetchLastFire } from "@/lib/hooks/use-schedules";
import type { LastFire, Schedule } from "./schedule-types";
import {
  describeShape, formatWhen, nextFireLabel, outcomeLabel, OUTCOME_TONE,
  STATE_LABEL, STATE_TONE,
} from "./schedule-presenters";

type Pending = "pause" | "resume" | "remove" | "trigger" | null;

/**
 * Schedule detail. Offers exactly the lifecycle actions the backend supports
 * — pause/resume (state-aware), run now, delete — each fenced by the record's
 * revision. A conflict refresh or a deleted schedule surfaces truthful copy,
 * never a fabricated success. The heading is focusable so a deep-link focus
 * lands assistive tech on the right place.
 */
export function ScheduleDetail({
  schedule, focusOnMount, onFocusHandled, onClose, actions,
}: {
  schedule: Schedule;
  focusOnMount: boolean;
  onFocusHandled: () => void;
  onClose: () => void;
  actions: {
    pause: (s: Schedule) => Promise<ActionResult>;
    resume: (s: Schedule) => Promise<ActionResult>;
    remove: (s: Schedule) => Promise<ActionResult>;
    trigger: (s: Schedule) => Promise<ActionResult>;
  };
}) {
  const [pending, setPending] = useState<Pending>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastFire, setLastFire] = useState<LastFire | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (focusOnMount) {
      headingRef.current?.focus();
      onFocusHandled();
    }
  }, [focusOnMount, onFocusHandled]);

  useEffect(() => {
    let live = true;
    setLastFire(null);
    void fetchLastFire(schedule).then((fire) => { if (live) setLastFire(fire); });
    return () => { live = false; };
  }, [schedule]);

  const paused = schedule.state === "paused" || schedule.state === "auto_paused";
  const run = async (kind: Exclude<Pending, null>, fn: () => Promise<ActionResult>) => {
    setPending(kind); setNotice(null);
    const result = await fn();
    setPending(null);
    if (result.status === "conflict") setNotice("This schedule changed elsewhere — refreshed to the latest.");
    else if (result.status === "deleted") setNotice("This schedule no longer exists.");
    else if (result.status === "error") setNotice("That action didn't go through. Try again.");
    else if (kind === "remove") setNotice(null);
  };

  return (
    <article className="rounded-xl border border-violet-500/30 bg-violet-500/[0.04] p-4">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 ref={headingRef} tabIndex={-1} className="truncate font-medium outline-none">
            {schedule.agentId}
          </h2>
          <p className="truncate text-xs text-muted-foreground">{schedule.scheduleId}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${STATE_TONE[schedule.state]}`}>
            {STATE_LABEL[schedule.state]}
          </span>
          <button type="button" onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">
            Close
          </button>
        </div>
      </header>

      {notice && (
        <div role="status" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
          {notice}
        </div>
      )}

      <dl className="mb-4 grid gap-2 text-sm sm:grid-cols-2">
        <Field label="Runs" value={describeShape(schedule)} />
        <Field label="Next fire" value={nextFireLabel(schedule)} />
        <Field label="Last fire" value={formatWhen(schedule.lastFireAt)} />
        <Field
          label="Last outcome"
          value={lastFire ? outcomeLabel(lastFire.outcome) : schedule.fireSequence > 0 ? "Recorded" : "Not run yet"}
          tone={lastFire ? OUTCOME_TONE[lastFire.outcome] : undefined}
        />
      </dl>

      <div className="mb-4 rounded-lg border border-border/40 bg-card/30 p-3">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground/60">Task</p>
        <p className="mt-1 whitespace-pre-wrap break-words text-sm text-foreground/90">{schedule.task}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <ActionButton
          label="Run now" busy={pending === "trigger"} disabled={pending !== null || schedule.state !== "active"}
          onClick={() => run("trigger", () => actions.trigger(schedule))} icon={Play}
        />
        {paused ? (
          <ActionButton
            label="Resume" busy={pending === "resume"} disabled={pending !== null}
            onClick={() => run("resume", () => actions.resume(schedule))} icon={Play}
          />
        ) : (
          <ActionButton
            label="Pause" busy={pending === "pause"} disabled={pending !== null || schedule.state === "completed"}
            onClick={() => run("pause", () => actions.pause(schedule))} icon={Pause}
          />
        )}
        <ActionButton
          label="Delete" busy={pending === "remove"} disabled={pending !== null} tone="danger"
          onClick={() => run("remove", () => actions.remove(schedule))} icon={Trash2}
        />
      </div>
    </article>
  );
}

function Field({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground/60">{label}</dt>
      <dd className={`m-0 truncate text-sm ${tone ?? "text-foreground/90"}`} title={value}>{value}</dd>
    </div>
  );
}

function ActionButton({ label, onClick, busy, disabled, icon: Icon, tone }: {
  label: string; onClick: () => void; busy: boolean; disabled: boolean;
  icon: typeof Play; tone?: "danger";
}) {
  return (
    <button
      type="button" onClick={onClick} disabled={disabled} aria-label={label}
      className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors disabled:opacity-50 ${
        tone === "danger"
          ? "border-destructive/40 text-destructive hover:bg-destructive/10"
          : "border-border/60 hover:bg-muted/50"
      }`}
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}
