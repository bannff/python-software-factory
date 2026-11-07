/** Truthful empty-state copy: names the active constraint instead of implying no sessions exist. */
export function emptyMessage(query: string, filter: string, includeArchived: boolean): string {
  if (query.trim()) return "No sessions match your search.";
  if (filter === "unread") return "No unread sessions.";
  if (filter !== "all") return "No sessions match this filter.";
  return includeArchived
    ? "No sessions yet. Start a chat to create one."
    : "No active sessions. Start a chat, or show archived sessions.";
}
