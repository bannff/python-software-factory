/**
 * Chat-feedback helpers (bd-2dq6; rewired bd:python-factory-pfvo9 S2).
 *
 * Publishes thumbs-up / thumbs-down as a `chat.feedback` event on the
 * Companion-X events bus (via the existing /api/tools/events_publish
 * proxy). The backend `chat_feedback_dispatch` subscription turns it into
 * a reward signal through the learning user-feedback source — up mints +
 * stores a learning, down stores a PENALIZED learning. This replaces the
 * old dead-end direct `memory_memory_store` write.
 *
 * Side-effects (toast confirmation) live in the chat-callbacks module
 * so this file stays import-light and testable.
 */

import { callTool } from "@/lib/api";
import type { CanvasViewId } from "@/lib/types";

export type FeedbackVerdict = "up" | "down";

export interface FeedbackPayload {
  threadId: string;
  messageId: string;
  verdict: FeedbackVerdict;
  /** Active persona id (companion_x_agent_id) the feedback is about. */
  agentId?: string;
  /** Snapshot of the user-visible content at the time of feedback. */
  content?: string;
  /** Active canvas view when the feedback was given (helps triage). */
  activeView?: CanvasViewId;
}

/**
 * Emit a thumbs verdict as a `chat.feedback` event.
 *
 * The backend learning user-feedback source maps up→+1.0 / down→-1.0; the
 * persona `agentId` rides as `domain_class` so the stored learning is
 * tagged `{agentId}-learnings` and recalled by that persona next turn.
 */
export async function persistFeedback(payload: FeedbackPayload): Promise<void> {
  const { threadId, messageId, verdict, agentId, content, activeView } = payload;
  const summary = (content ?? "").trim().slice(0, 280);
  const response = await callTool("events_publish", {
    event_type: "chat.feedback",
    source: "next-dashboard-chat",
    principal_id: "kiro-agent",
    payload: {
      verdict,
      agent_id: agentId ?? "",
      thread_id: threadId,
      message_id: messageId,
      content: summary,
      active_view: activeView ?? null,
    },
  });
  // Brick returned HTTP 200 but logical failure — surface as an error
  // so the caller can toast a non-success message.
  const inner = response.result;
  if (
    inner &&
    typeof inner === "object" &&
    "error" in inner &&
    (inner as { error?: unknown }).error
  ) {
    throw new Error(String((inner as { error?: unknown }).error));
  }
}
