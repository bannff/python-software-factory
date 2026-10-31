import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Client-side model + parsers for the durable Notification inbox
 * (``notification_inbox_list`` etc.). The frontend renders only plain
 * title/body/timestamp/priority — never raw IDs, reason codes, tenant/owner,
 * or the record's ``kind`` discriminator. Targets are the backend's closed
 * union; only kinds with existing, safe frontend navigation resolve to a route.
 */

export type NotificationPriority = "passive" | "default" | "critical";

export type NotificationTargetKind =
  | "session" | "workflow_run" | "schedule"
  | "artifact" | "crew" | "lesson" | "canvas";

export interface NotificationTarget {
  kind: NotificationTargetKind;
  id: string;
}

export interface InboxNotification {
  notificationId: string;
  title: string;
  body: string;
  priority: NotificationPriority;
  target: NotificationTarget;
  createdAt: string;
  read: boolean;
  revision: number;
}

const PRIORITIES = new Set<NotificationPriority>(["passive", "default", "critical"]);

/** The single canonical-ID field each closed target variant exposes. */
const TARGET_ID_FIELD: Record<NotificationTargetKind, string> = {
  session: "session_id", workflow_run: "run_id", schedule: "schedule_id",
  artifact: "slug", crew: "crew_id", lesson: "lesson_id", canvas: "view_id",
};

function parseTarget(raw: unknown): NotificationTarget | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const kind = obj.kind;
  if (typeof kind !== "string" || !(kind in TARGET_ID_FIELD)) return null;
  const id = obj[TARGET_ID_FIELD[kind as NotificationTargetKind]];
  if (typeof id !== "string") return null;
  return { kind: kind as NotificationTargetKind, id };
}

function parseRecord(raw: unknown): InboxNotification | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  if (typeof row.notification_id !== "string" || typeof row.title !== "string") return null;
  const target = parseTarget(row.target);
  if (!target) return null;
  return {
    notificationId: row.notification_id,
    title: row.title,
    body: typeof row.body === "string" ? row.body : "",
    priority: PRIORITIES.has(row.priority as NotificationPriority)
      ? (row.priority as NotificationPriority)
      : "default",
    target,
    createdAt: typeof row.created_at === "string" ? row.created_at : "",
    read: row.read_at != null,
    revision: typeof row.revision === "number" ? row.revision : 1,
  };
}

/** Unwrap + validate a ``notification_inbox_list`` ToolResult. */
export function parseInbox(raw: unknown): InboxNotification[] {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const rows = Array.isArray(obj.notifications) ? obj.notifications : [];
  return rows
    .map(parseRecord)
    .filter((record): record is InboxNotification => record !== null);
}

export function unreadCount(items: InboxNotification[]): number {
  return items.reduce((total, item) => (item.read ? total : total + 1), 0);
}

/**
 * Internal route for a target the topbar can safely navigate to today, or
 * ``null`` when navigation is not yet wired for that target kind.
 */
export function targetRoute(target: NotificationTarget): string | null {
  if (target.kind === "session") return `/sessions/${encodeURIComponent(target.id)}`;
  if (target.kind === "schedule") return `/schedules/${encodeURIComponent(target.id)}`;
  if (target.kind === "lesson") return `/lessons/${encodeURIComponent(target.id)}`;
  if (target.kind === "artifact") return `/artifacts/${encodeURIComponent(target.id)}`;
  if (target.kind === "crew") return `/crews/${encodeURIComponent(target.id)}`;
  return null;
}

export function formatTimestamp(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
