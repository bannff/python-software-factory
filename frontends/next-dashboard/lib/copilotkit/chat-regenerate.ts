import type { Message } from "@ag-ui/core";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import { parseSession } from "@/lib/hooks/use-session-list";
import { loadSessionHistory } from "@/lib/hooks/use-session-history";

type Caller = typeof callTool;

/** Row 16 (feature-map): re-run the reply to ``messageId`` with
 * ``newPrompt`` onto a genuine NEW sibling checkpoint branch — the
 * ORIGINAL reply stays durably resumable, never overwritten.
 *
 * The backend call ALREADY performs the real generation (a full
 * ``LangChainAgentRuntime.invoke()``) and persists the result as the
 * thread's new "current" checkpoint — so the caller must NOT also call
 * ``copilotkit.runAgent`` afterward; that would be a second, duplicate
 * generation against the same prompt. Instead, on success this re-reads
 * the REAL durable transcript (``loadSessionHistory``, the same primitive
 * the Sessions page itself uses) so the caller can set it verbatim —
 * reflecting the server's own answer, not generating a second one.
 *
 * Returns the new transcript on success, or ``null`` when ``messageId``
 * was never found in this thread's checkpoint chain (a truthful no-op).
 */
export async function regenerateTurn(
  threadId: string, messageId: string, newPrompt: string, caller: Caller = callTool,
): Promise<Message[] | null> {
  const session = parseSession(await caller("session_resolve_thread", { thread_id: threadId }));
  const data = unwrapToolData(await caller("session_regenerate", {
    session_id: session.session_id, message_id: messageId, new_prompt: newPrompt,
    expected_revision: session.revision,
  })) as { regenerated?: boolean } | undefined;
  if (data?.regenerated !== true) return null;
  return loadSessionHistory(session.session_id);
}
