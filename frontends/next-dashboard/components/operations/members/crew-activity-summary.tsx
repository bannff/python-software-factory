"use client";

import { foldActivityByDay, type ActivityEvent } from "./activity-days";

/**
 * Row 30 (feature-map) — the Crew summary's activity view (presentational).
 *
 * Composes the pure `foldActivityByDay` model (cycle 19) into the Crew
 * summary readout: the member's recent activity folded by calendar day, with
 * a per-day count, per-project breakdown, and a floor marker ("≥ N") on the
 * oldest day when the source log was capped. Given events it renders; the
 * activity DATA source (a member activity endpoint) is deferred.
 */
export function CrewActivitySummary({ events, capped, now }: {
  events: readonly ActivityEvent[];
  capped?: boolean;
  now?: number;
}) {
  const days = foldActivityByDay(events, { capped, now });
  if (days.length === 0) {
    return <p className="text-sm italic text-muted-foreground/70">No recent activity.</p>;
  }
  return (
    <ul aria-label="Activity by day" className="flex flex-col gap-2">
      {days.map((day) => (
        <li key={day.dayKey} className="rounded-md border border-border/40 p-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium">{day.label}</span>
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {day.floored ? `≥ ${day.count}` : day.count}
            </span>
          </div>
          {day.byProject.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {day.byProject.map((p) => (
                <span key={p.project}
                  className="rounded-full border border-border/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {p.project} · {p.count}
                </span>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
