import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import { parseSession } from "@/lib/hooks/use-session-list";

type Caller = typeof callTool;

/** Row 15 (feature-map): drop the transcript back to right after
 * ``messageId`` landed — generates nothing new (unlike Regenerate).
 *
 * The chat sidebar only carries ``thread_id`` (via CopilotKit's
 * ``agent.threadId``), not the session brick's own ``session_id`` — so
 * this resolves the owning session first (``session_resolve_thread``,
 * the same thread-scoped lookup ``session_stop`` established for row
 * 61) before calling the agent brick's cross-brick ``session_rewind``
 * tool with its ``session_id``/``revision``.
 *
 * Returns ``true`` when the rewind actually happened, ``false`` when
 * ``messageId`` was never found in this thread's checkpoint chain (a
 * truthful no-op, not an error — the caller should tell the user
 * nothing moved rather than silently pretending it did).
 */
export async function rewindToMessage(
  threadId: string, messageId: string, caller: Caller = callTool,
): Promise<boolean> {
  const session = parseSession(await caller("session_resolve_thread", { thread_id: threadId }));
  const data = unwrapToolData(await caller("session_rewind", {
    session_id: session.session_id, message_id: messageId,
    expected_revision: session.revision,
  })) as { rewound?: boolean } | undefined;
  return data?.rewound === true;
}
