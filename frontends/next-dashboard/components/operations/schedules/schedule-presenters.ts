import type { FireOutcome, Schedule, ScheduleState } from "./schedule-types";

/**
 * Plain-language presenters for the Schedules surface. Every mapping turns a
 * typed backend value into human copy — a first-time user never sees a raw
 * state string, cron code, or fire enum. Styling tones use theme tokens.
 */

export const STATE_LABEL: Record<ScheduleState, string> = {
  active: "Active",
  paused: "Paused",
  auto_paused: "Auto-paused",
  completed: "Completed",
};

export const STATE_TONE: Record<ScheduleState, string> = {
  active: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  paused: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  auto_paused: "border-orange-500/40 bg-orange-500/10 text-orange-300",
  completed: "border-border/60 bg-muted/40 text-muted-foreground",
};

const OUTCOME_LABEL: Record<FireOutcome, string> = {
  succeeded: "Last run succeeded",
  failed: "Last run failed",
  cancelled: "Last run cancelled",
  running: "Running now",
};

export const OUTCOME_TONE: Record<FireOutcome, string> = {
  succeeded: "text-emerald-400",
  failed: "text-destructive",
  cancelled: "text-muted-foreground",
  running: "text-violet-400",
};

export function outcomeLabel(outcome: FireOutcome): string {
  return OUTCOME_LABEL[outcome];
}

/** Human description of the schedule's shape — no raw cron/kind codes. */
export function describeShape(schedule: Schedule): string {
  if (schedule.kind === "interval" && schedule.intervalSeconds) {
    return `Every ${describeInterval(schedule.intervalSeconds)}`;
  }
  if (schedule.kind === "one_shot") {
    return schedule.oneShotAt ? `Once, at ${formatWhen(schedule.oneShotAt)}` : "Runs once";
  }
  const tz = schedule.timezone && schedule.timezone !== "UTC" ? ` (${schedule.timezone})` : "";
  return `On a repeating schedule${tz}`;
}

function describeInterval(seconds: number): string {
  if (seconds % 86_400 === 0) return plural(seconds / 86_400, "day");
  if (seconds % 3_600 === 0) return plural(seconds / 3_600, "hour");
  if (seconds % 60 === 0) return plural(seconds / 60, "minute");
  return plural(seconds, "second");
}

function plural(value: number, unit: string): string {
  return value === 1 ? `${unit}` : `${value} ${unit}s`;
}

/** Coarse, record-only outcome for the list (no per-row fire fetch). */
export function listOutcome(schedule: Schedule): { label: string; tone: string } {
  if (schedule.consecutiveFailures > 0) {
    return { label: "Needs attention", tone: "text-destructive" };
  }
  if (schedule.fireSequence > 0) return { label: "Ran cleanly", tone: "text-emerald-400" };
  return { label: "Not run yet", tone: "text-muted-foreground" };
}

/** Absolute local time; falsy input renders an em dash. */
export function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

/** Relative time such as "in 5 min" / "3 h ago"; stable, no seconds churn. */
export function formatRelative(iso: string | null, now: number = Date.now()): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const deltaMs = then - now;
  const future = deltaMs >= 0;
  const abs = Math.abs(deltaMs);
  const value = pickUnit(abs);
  if (!value) return "just now";
  return future ? `in ${value}` : `${value} ago`;
}

function pickUnit(ms: number): string | null {
  const mins = Math.round(ms / 60_000);
  if (mins < 1) return null;
  if (mins < 60) return `${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} h`;
  const days = Math.round(hours / 24);
  return `${days} d`;
}

/** What to show under "Next fire" given the schedule's state. */
export function nextFireLabel(schedule: Schedule, now?: number): string {
  if (schedule.state === "completed") return "Complete — won't run again";
  if (schedule.state === "paused" || schedule.state === "auto_paused") {
    return "Paused — not scheduled";
  }
  if (!schedule.nextFireAt) return "Not scheduled";
  return `${formatRelative(schedule.nextFireAt, now)} · ${formatWhen(schedule.nextFireAt)}`;
}
