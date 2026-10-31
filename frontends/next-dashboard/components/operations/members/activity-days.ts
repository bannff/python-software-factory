/**
 * Row 30 (feature-map) — Crew summary activity folding.
 *
 * The row names `pages/members/activityDays.ts` as "pure helpers: fold the
 * activity log by local day, label days, cap floors — no feature of its own."
 * This is that: given a member's activity events, bucket them by LOCAL
 * calendar day (newest first), count per day and per project, label each day
 * (Today / Yesterday / "Mon D"), and mark the oldest day as a floor when the
 * source log was capped (so its count reads as a lower bound, not a total).
 *
 * Pure and time-injectable (`now`) so it is fully unit-testable and free of
 * locale/timezone-dependent formatting. The data source (a member activity
 * endpoint) is deferred; this model consumes events, it does not fetch them.
 */

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

export interface ActivityEvent {
  /** Epoch ms. */
  at: number;
  /** Optional project the activity belonged to. */
  project?: string;
}

export interface ProjectCount {
  project: string;
  count: number;
}

export interface ActivityDay {
  /** Local `YYYY-MM-DD` bucket key. */
  dayKey: string;
  /** "Today" | "Yesterday" | "Mon D". */
  label: string;
  count: number;
  byProject: ProjectCount[];
  /** True when this day's count is a floor (source log was capped). */
  floored: boolean;
}

function dayKeyLocal(ts: number): string {
  const d = new Date(ts);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function labelFor(ts: number, nowKey: string, yesterdayKey: string): string {
  const key = dayKeyLocal(ts);
  if (key === nowKey) return "Today";
  if (key === yesterdayKey) return "Yesterday";
  const d = new Date(ts);
  return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

/**
 * Fold `events` into per-local-day buckets, newest day first.
 * `opts.capped` marks the oldest day's count as a floor (log truncated).
 * `opts.now` (default `Date.now()`) drives the Today/Yesterday labels.
 */
export function foldActivityByDay(
  events: readonly ActivityEvent[],
  opts: { now?: number; capped?: boolean } = {},
): ActivityDay[] {
  const now = opts.now ?? Date.now();
  const nowKey = dayKeyLocal(now);
  const yesterdayKey = dayKeyLocal(now - 86_400_000);

  const buckets = new Map<string, { ts: number; count: number; projects: Map<string, number> }>();
  for (const event of events) {
    const key = dayKeyLocal(event.at);
    let bucket = buckets.get(key);
    if (!bucket) {
      bucket = { ts: event.at, count: 0, projects: new Map() };
      buckets.set(key, bucket);
    }
    bucket.count += 1;
    // Keep a representative ts for labelling (any event in the day works).
    if (event.project) bucket.projects.set(event.project, (bucket.projects.get(event.project) ?? 0) + 1);
  }

  const days = [...buckets.entries()]
    .map(([dayKey, b]) => ({
      dayKey,
      label: labelFor(b.ts, nowKey, yesterdayKey),
      count: b.count,
      byProject: [...b.projects.entries()]
        .map(([project, count]) => ({ project, count }))
        .sort((a, z) => z.count - a.count || a.project.localeCompare(z.project)),
      floored: false,
    }))
    .sort((a, z) => (a.dayKey < z.dayKey ? 1 : a.dayKey > z.dayKey ? -1 : 0));

  if (opts.capped && days.length > 0) {
    days[days.length - 1].floored = true; // oldest day is incomplete
  }
  return days;
}
