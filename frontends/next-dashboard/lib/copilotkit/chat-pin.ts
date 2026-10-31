import { callTool } from "@/lib/api";
import { parseSession } from "@/lib/hooks/use-session-list";

type Caller = typeof callTool;

/** Row 9 (feature-map): toggle a message's pinned state for its session.
 *
 * The chat sidebar only carries ``thread_id`` (via CopilotKit's
 * ``agent.threadId``), not the session brick's own ``session_id`` — so
 * this resolves the owning session first (``session_resolve_thread``, the
 * same thread-scoped lookup rows 15/16 use), reads its current pinned set,
 * and rewrites the WHOLE set (add the id if absent, remove it if present)
 * through the revision-fenced ``session_set_pinned_messages`` tool. Whole-
 * set replacement, not a partial add/remove, matches the backend tool's own
 * atomic-CAS contract (``SetPinnedInput`` takes the full membership).
 *
 * Returns whether the message is pinned AFTER the toggle, so the caller can
 * report "pinned" vs "unpinned" truthfully rather than guessing.
 */
export async function togglePinnedMessage(
  threadId: string, messageId: string, caller: Caller = callTool,
): Promise<boolean> {
  const session = parseSession(await caller("session_resolve_thread", { thread_id: threadId }));
  const current = session.pinned_message_ids;
  const next = current.includes(messageId)
    ? current.filter((id) => id !== messageId)
    : [...current, messageId];
  const updated = parseSession(await caller("session_set_pinned_messages", {
    session_id: session.session_id, pinned_message_ids: next,
    expected_revision: session.revision,
  }));
  return updated.pinned_message_ids.includes(messageId);
}
