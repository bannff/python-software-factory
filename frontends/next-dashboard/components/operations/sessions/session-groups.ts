import type { SessionSummary } from "@/lib/hooks/use-session-list";

export interface SessionGroup {
  id: "pinned" | "today" | "yesterday" | "week" | "older";
  label: string;
  sessions: SessionSummary[];
}

const DAY = 86_400_000;

export function groupSessions(
  sessions: readonly SessionSummary[], now = Date.now(),
): SessionGroup[] {
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const today = start.getTime();
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
    const age = Number.isFinite(updated) ? today - updated : Number.POSITIVE_INFINITY;
    const index = updated >= today ? 1 : age < DAY ? 2 : age < DAY * 7 ? 3 : 4;
    groups[index].sessions.push(session);
  }
  return groups.filter((group) => group.sessions.length > 0);
}
