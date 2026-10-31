"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { callTool } from "@/lib/api";
import {
  parseInbox, targetRoute, unreadCount, type InboxNotification,
} from "@/lib/notifications";

const POLL_MS = 30_000;

export interface OpenState {
  status: "idle" | "unavailable";
  message: string;
}

/**
 * Owner-scoped inbox state. Identity is ambient on the backend — no
 * tenant/owner is ever sent. Mark-one uses record revision; mark-all is fenced
 * by the observed unread count. A CAS/count conflict refreshes the truth rather
 * than reporting a fake success. Only targets with an internal route navigate.
 */
export function useInbox() {
  const router = useRouter();
  const [items, setItems] = useState<InboxNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openState, setOpenState] = useState<OpenState>({ status: "idle", message: "" });
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const parsed = parseInbox(
        await callTool("notification_inbox_list", { limit: 50, offset: 0 }),
      );
      if (!mounted.current) return;
      setItems(parsed);
      setError(null);
    } catch {
      if (mounted.current) setError("Notifications unavailable");
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => { mounted.current = false; clearInterval(timer); };
  }, [refresh]);

  const unread = useMemo(() => unreadCount(items), [items]);

  const markRead = useCallback(async (item: InboxNotification) => {
    if (item.read) return;
    try {
      await callTool("notification_inbox_mark_read", {
        notification_id: item.notificationId,
        expected_revision: item.revision,
      });
    } catch {
      // Stale/foreign — fall through to refresh, never a fabricated state.
    }
    await refresh();
  }, [refresh]);

  const markAll = useCallback(async () => {
    if (unread === 0) return;
    try {
      await callTool("notification_inbox_mark_all_read", {
        expected_unread_count: unread,
      });
    } catch {
      // Drifted count conflict — refresh the truth instead of lying.
    }
    await refresh();
  }, [refresh, unread]);

  const clearOpenState = useCallback(
    () => setOpenState({ status: "idle", message: "" }), [],
  );

  const openTarget = useCallback(async (item: InboxNotification) => {
    const route = targetRoute(item.target);
    if (!route) {
      setOpenState({ status: "unavailable", message: "This item can’t be opened here yet." });
      return;
    }
    try {
      await callTool("notification_inbox_resolve_target", {
        notification_id: item.notificationId,
      });
    } catch {
      setOpenState({ status: "unavailable", message: "This item no longer exists." });
      return;
    }
    router.push(route);
  }, [router]);

  return {
    items, loading, error, unread,
    refresh, markRead, markAll, openTarget, openState, clearOpenState,
  };
}
