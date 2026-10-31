import type { SessionSummary } from "@/lib/hooks/use-session-list";

/** Compact relative-time label, mirroring SessionDeck's wording. */
export function relativeTime(value: string): string {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return "unknown";
  const seconds = Math.max(0, (Date.now() - parsed) / 1000);
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

/**
 * Human agent label. Never surfaces a raw slug as-is when it can be
 * softened; callers pass a resolved persona name when they have one.
 */
export function agentLabel(session: SessionSummary, resolved?: string): string {
  if (resolved && resolved.trim()) return resolved;
  return session.agent_id.replaceAll("-", " ").replaceAll("_", " ");
}

/** A session is archived when the backend stamped an archived_at time. */
export function isArchived(session: SessionSummary): boolean {
  return typeof session.archived_at === "string" && session.archived_at.length > 0;
}
