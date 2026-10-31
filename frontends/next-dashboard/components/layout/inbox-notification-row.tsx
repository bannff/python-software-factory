"use client";

import { Badge } from "@/components/ui/badge";
import { formatTimestamp, type InboxNotification } from "@/lib/notifications";

const PRIORITY_VARIANT: Record<
  InboxNotification["priority"], "secondary" | "default" | "destructive"
> = {
  passive: "secondary",
  default: "default",
  critical: "destructive",
};

/**
 * One inbox row. Renders only plain title, body, timestamp, and priority —
 * never the notification ID, target ID, or a reason code.
 */
export function InboxRow({ notification, onMarkRead, onOpen }: {
  notification: InboxNotification;
  onMarkRead: () => void;
  onOpen: () => void;
}) {
  const { title, body, priority, createdAt, read } = notification;
  const timestamp = formatTimestamp(createdAt);
  return (
    <li className="px-4 py-3">
      <div className="flex items-start gap-2">
        {!read && (
          <span aria-label="Unread" className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-violet-500" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className={`truncate text-sm ${read ? "font-normal" : "font-medium"}`} title={title}>
              {title}
            </p>
            {priority !== "default" && (
              <Badge variant={PRIORITY_VARIANT[priority]} className="shrink-0 text-[10px] capitalize">
                {priority}
              </Badge>
            )}
          </div>
          {body && <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{body}</p>}
          {timestamp && <p className="mt-1 text-[11px] text-muted-foreground/70">{timestamp}</p>}
          <div className="mt-2 flex gap-3 text-xs">
            <button type="button" onClick={onOpen} className="text-violet-400 hover:text-violet-300">
              Open
            </button>
            {!read && (
              <button type="button" onClick={onMarkRead} className="text-muted-foreground hover:text-foreground">
                Mark read
              </button>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}
