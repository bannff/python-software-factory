import type { SessionSummary } from "@/lib/hooks/use-session-list";

export interface SessionGroup {
  id: "pinned" | "today" | "yesterday" | "week" | "older";
  label: string;
  sessions: SessionSummary[];
}

/** Local midnight `daysAgo` calendar days before `now`; setDate keeps 23/25-hour clock-change days exact. */
function startOfDay(now: number, daysAgo: number): number {
  const day = new Date(now);
  day.setHours(0, 0, 0, 0);
  day.setDate(day.getDate() - daysAgo);
  return day.getTime();
}

export function groupSessions(
  sessions: readonly SessionSummary[], now = Date.now(),
): SessionGroup[] {
  const today = startOfDay(now, 0);
  const yesterday = startOfDay(now, 1);
  const weekStart = startOfDay(now, 7);
  const groups: SessionGroup[] = [
    { id: "pinned", label: "Pinned", sessions: [] },
    { id: "today", label: "Today", sessions: [] },
    { id: "yesterday", label: "Yesterday", sessions: [] },
    { id: "week", label: "Previous 7 days", sessions: [] },
    { id: "older", label: "Older", sessions: [] },
  ];
  for (const session of sessions) {
    if (session.pinned_rank !== null) {
      groups[0].sessions.push(session);
      continue;
    }
    const updated = Date.parse(session.updated_at);
    const index = !Number.isFinite(updated) ? 4
      : updated >= today ? 1 : updated >= yesterday ? 2 : updated >= weekStart ? 3 : 4;
    groups[index].sessions.push(session);
  }
  return groups.filter((group) => group.sessions.length > 0);
}
