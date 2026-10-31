import { useMemo } from "react";
import type { SessionSummary } from "@/lib/hooks/use-session-list";
import { groupSessions } from "./session-groups";

/**
 * Derived list/filter/pinned-navigation state for ``SessionsView``. Split
 * out to keep that file under the 200 LOC ceiling — pure derivation, no
 * side effects, so a plain function-of-props hook is the right shape.
 */
export function useSessionsViewDerived(
  sessions: SessionSummary[], overrides: Record<string, SessionSummary>,
  query: string, filter: string, selectedId: string | null,
) {
  const merged = useMemo(
    () => sessions.map((session) => overrides[session.session_id] ?? session),
    [sessions, overrides],
  );
  const tagFilters = useMemo(() => [...new Set(merged.flatMap((session) => session.tags))].sort(), [merged]);
  const folderFilters = useMemo(
    () => [...new Set(merged.map((session) => session.folder).filter(Boolean))].sort(), [merged]);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return merged.filter((session) => {
      const matchesFilter = filter === "all" ? true
        : filter === "unread" ? session.unread
        : filter.startsWith("folder:") ? session.folder === filter.slice(7)
        : session.tags.includes(filter.slice(4));
      return session.title.toLowerCase().includes(needle) && matchesFilter;
    });
  }, [filter, merged, query]);
  const groups = useMemo(() => groupSessions(visible), [visible]);
  const selected = visible.find((session) => session.session_id === selectedId) ?? null;
  const pinned = visible.filter((session) => session.pinned_rank !== null);
  const pinnedIndex = selected ? pinned.findIndex((session) => session.session_id === selected.session_id) : -1;
  const moveUpBeforeId = pinnedIndex > 0 ? pinned[pinnedIndex - 1].session_id : undefined;
  const moveDownBeforeId = pinnedIndex >= 0 && pinnedIndex < pinned.length - 1
    ? pinned[pinnedIndex + 2]?.session_id ?? null : undefined;

  return { merged, tagFilters, folderFilters, visible, groups, selected, moveUpBeforeId, moveDownBeforeId };
}
