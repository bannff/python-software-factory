"use client";

import * as Popover from "@radix-ui/react-popover";
import { Bell, Loader2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useInbox } from "@/lib/hooks/use-inbox";
import { InboxRow } from "./inbox-notification-row";

/**
 * Compact topbar notification inbox (M7 Option A). A named, keyboard-operable
 * Bell control with an unread badge and a polite live region; the Radix popover
 * supplies focus trap, Esc-to-close, and return-focus. The panel is ~360px with
 * a bounded scroll and truthful loading/empty/error/retry states.
 */
export function InboxPopover() {
  const {
    items, loading, error, unread,
    refresh, markAll, markRead, openTarget, openState,
  } = useInbox();

  return (
    <div className="flex items-center">
      <Popover.Root onOpenChange={(open) => { if (open) void refresh(); }}>
        <Popover.Trigger asChild>
          <button
            type="button"
            aria-label={unread > 0 ? `Notifications, ${unread} unread` : "Notifications"}
            className="relative flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Bell className="h-4 w-4" />
            {unread > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-violet-500 px-1 text-[10px] font-semibold text-white">
                {unread > 99 ? "99+" : unread}
              </span>
            )}
          </button>
        </Popover.Trigger>
        <span className="sr-only" role="status" aria-live="polite">
          {unread > 0 ? `${unread} unread notifications` : "No unread notifications"}
        </span>
        <Popover.Portal>
          <Popover.Content
            align="end"
            sideOffset={8}
            aria-label="Notifications"
            className="z-50 w-[360px] overflow-hidden rounded-lg border border-border/50 bg-card/95 shadow-xl backdrop-blur-xl"
          >
            <header className="flex items-center justify-between border-b border-border/50 px-4 py-2.5">
              <h2 className="text-sm font-semibold">Notifications</h2>
              <button
                type="button"
                onClick={() => void markAll()}
                disabled={unread === 0}
                className="text-xs text-violet-400 transition-colors hover:text-violet-300 disabled:opacity-40 disabled:hover:text-violet-400"
              >
                Mark all read
              </button>
            </header>

            {openState.status === "unavailable" && (
              <p role="status" className="border-b border-border/50 bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
                {openState.message}
              </p>
            )}

            {loading && items.length === 0 && !error && (
              <div className="flex items-center justify-center gap-2 px-4 py-8 text-xs text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading…
              </div>
            )}

            {error && (
              <div role="alert" className="flex flex-col items-start gap-2 px-4 py-6 text-xs">
                <span className="text-muted-foreground">Notifications unavailable.</span>
                <button
                  type="button"
                  onClick={() => void refresh()}
                  className="rounded-md border border-border/60 px-3 py-1.5 hover:bg-muted/50"
                >
                  Retry
                </button>
              </div>
            )}

            {!loading && !error && items.length === 0 && (
              <p className="px-4 py-8 text-center text-xs text-muted-foreground">
                You’re all caught up.
              </p>
            )}

            {!error && items.length > 0 && (
              <ScrollArea className="max-h-[60vh]">
                <ul className="divide-y divide-border/40">
                  {items.map((item) => (
                    <InboxRow
                      key={item.notificationId}
                      notification={item}
                      onMarkRead={() => void markRead(item)}
                      onOpen={() => void openTarget(item)}
                    />
                  ))}
                </ul>
              </ScrollArea>
            )}
          </Popover.Content>
        </Popover.Portal>
      </Popover.Root>
    </div>
  );
}
