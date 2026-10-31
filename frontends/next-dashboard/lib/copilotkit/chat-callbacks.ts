"use client";

/**
 * Chat-message-toolbar callbacks (bd-2dq6).
 *
 * Centralises the four callback shapes the v2 SDK exposes via
 * `<CopilotChatAssistantMessage>` / `<CopilotChatUserMessage>` slot
 * props so `<CopilotChatSidebar>` stays focused on layout:
 *   - onThumbsUp / onThumbsDown → persist to memory + toast
 *   - onRegenerate → re-run via the real backend (row 16), reflect its
 *     own returned transcript — never a second client-side generation
 *   - onEditMessage → swap a user message + drop everything after + re-run
 *   - onReadAloud → SpeechSynthesis (best-effort, no-op when unavailable)
 *   - onRewind → drop the transcript back via the real backend (row 15)
 *
 * The hook returns plain functions that close over the agent + workbench,
 * matching the AG-UI message types directly. CopilotKit v2 calls them
 * with `(message)` for assistant slots and `({ message })` for user
 * slots — see CopilotChatAssistantMessage / CopilotChatUserMessage.
 */

import { useCallback } from "react";
import type { AssistantMessage, Message, UserMessage } from "@ag-ui/core";
import { useAgent } from "@copilotkit/react-core/v2";
import { useCopilotKit } from "@copilotkit/react-core/v2";
import { toast } from "sonner";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { persistFeedback, type FeedbackVerdict } from "./chat-feedback";
import { regenerateTurn } from "./chat-regenerate";
import { rewindToMessage } from "./chat-rewind";
import { togglePinnedMessage } from "./chat-pin";
import { shareMessageAsCard } from "./share-card";

interface ChatCallbacks {
  onThumbsUp: (message: AssistantMessage) => void;
  onThumbsDown: (message: AssistantMessage) => void;
  onRegenerate: (message: AssistantMessage) => void;
  onEditMessage: (props: { message: UserMessage }) => void;
  onReadAloud: (message: AssistantMessage) => void;
  onRewind: (message: AssistantMessage) => void;
  onPin: (message: AssistantMessage) => void;
  onShare: (message: AssistantMessage) => void;
}

/** Find the index of a message by id, or -1. */
function indexOfMessage(messages: Message[], id: string): number {
  return messages.findIndex((m) => m.id === id);
}

/** Convert AG-UI content (string | parts[]) to plain text. */
function flattenContent(content: UserMessage["content"] | undefined): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  return content
    .map((p) => (typeof p === "object" && p && "text" in p && typeof (p as { text?: unknown }).text === "string" ? (p as { text: string }).text : ""))
    .filter(Boolean)
    .join("\n");
}

export function useChatCallbacks(agentId: string): ChatCallbacks {
  const { agent } = useAgent({ agentId });
  const { copilotkit } = useCopilotKit();
  const { activeView } = useWorkbenchContext();

  const sendFeedback = useCallback(
    async (verdict: FeedbackVerdict, message: AssistantMessage) => {
      try {
        const props = (copilotkit?.properties ?? {}) as Record<string, unknown>;
        const agentIdProp = props.companion_x_agent_id;
        await persistFeedback({
          threadId: agent.threadId,
          messageId: message.id,
          verdict,
          agentId:
            typeof agentIdProp === "string" && agentIdProp
              ? agentIdProp
              : "companion-x-default",
          content: typeof message.content === "string" ? message.content : "",
          activeView,
        });
        toast.success("Thanks, feedback saved", { duration: 1800 });
      } catch (err) {
        console.error("chat-feedback: persist failed", err);
        toast.error("Couldn't save feedback");
      }
    },
    [agent, copilotkit, activeView],
  );

  const onThumbsUp = useCallback(
    (m: AssistantMessage) => void sendFeedback("up", m),
    [sendFeedback],
  );
  const onThumbsDown = useCallback(
    (m: AssistantMessage) => void sendFeedback("down", m),
    [sendFeedback],
  );

  /**
   * Regenerate (row 16, feature-map): re-run the reply to this message
   * onto a genuine NEW sibling checkpoint branch — the ORIGINAL reply
   * stays durably resumable, never overwritten client-side-only the
   * way a plain "drop + re-run" would. The preceding user message's own
   * content is the prompt to regenerate with (upstream's own "re-run a
   * turn" contract, not a fresh prompt the owner types). The backend
   * call already performs the real generation, so this reflects the
   * server's own returned transcript — it must NOT also call
   * ``copilotkit.runAgent``, which would generate a SECOND reply.
   */
  const onRegenerate = useCallback(
    async (m: AssistantMessage) => {
      const idx = indexOfMessage(agent.messages, m.id);
      if (idx < 1) return;
      const prompt = flattenContent((agent.messages[idx - 1] as UserMessage)?.content);
      if (!prompt) return;
      try {
        const history = await regenerateTurn(agent.threadId, m.id, prompt);
        if (history === null) {
          toast.error("Couldn’t regenerate — this message wasn’t found in the saved history.");
          return;
        }
        agent.setMessages(history);
      } catch (err) {
        console.error("chat-callbacks: regenerate failed", err);
        toast.error("Regenerate failed");
      }
    },
    [agent],
  );

  /**
   * Edit a user message: keep the v2 SDK's edit dialog by relying on
   * its default EditButton (which already swaps in an inline editor);
   * here we just persist the swap. CopilotKit fires `onEditMessage`
   * once the user confirms the new content — at that point we drop
   * everything after the original message and re-run.
   *
   * In v2 1.53 the edit flow surfaces the new `message.content` on
   * the same `message` object; we accept that without optimistic
   * mutation to stay compatible with future versions.
   */
  const onEditMessage = useCallback(
    async ({ message }: { message: UserMessage }) => {
      const idx = indexOfMessage(agent.messages, message.id);
      if (idx < 0) return;
      // Replace the message at idx with the edited copy + drop trailing.
      const next = agent.messages.slice(0, idx);
      next.push({ ...message, content: flattenContent(message.content) });
      agent.setMessages(next);
      try {
        await copilotkit.runAgent({ agent });
      } catch (err) {
        console.error("chat-callbacks: edit re-run failed", err);
        toast.error("Couldn't re-run after edit");
      }
    },
    [agent, copilotkit],
  );

  /**
   * Read aloud: use the browser's SpeechSynthesis API. No-op when the
   * API isn't available (server-render, very old browsers) — keeps the
   * feature lightweight without bringing in a TTS dep.
   */
  const onReadAloud = useCallback((m: AssistantMessage) => {
    const text = typeof m.content === "string" ? m.content : "";
    if (!text || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const utter = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }, []);

  /**
   * Rewind (row 15, feature-map): drop the transcript back to right
   * after this message landed. Unlike Regenerate, nothing is re-run —
   * the durable ``active_checkpoint_id`` is moved server-side first
   * (so a reload resumes from the SAME point), then the trailing
   * client-side messages are dropped to match.
   */
  const onRewind = useCallback(
    async (m: AssistantMessage) => {
      try {
        const rewound = await rewindToMessage(agent.threadId, m.id);
        if (!rewound) {
          toast.error("Couldn’t rewind — this message wasn’t found in the saved history.");
          return;
        }
        const idx = indexOfMessage(agent.messages, m.id);
        if (idx >= 0) agent.setMessages(agent.messages.slice(0, idx + 1));
        toast.success("Rewound to this point", { duration: 1800 });
      } catch (err) {
        console.error("chat-callbacks: rewind failed", err);
        toast.error("Rewind failed");
      }
    },
    [agent],
  );

  /**
   * Pin (row 9, feature-map): toggle this message's pinned state for its
   * session. The whole pinned set is rewritten server-side (revision-fenced
   * ``session_set_pinned_messages``); the returned state drives a truthful
   * pinned/unpinned toast.
   */
  const onPin = useCallback(
    async (m: AssistantMessage) => {
      try {
        const pinned = await togglePinnedMessage(agent.threadId, m.id);
        toast.success(pinned ? "Message pinned" : "Message unpinned", { duration: 1800 });
      } catch (err) {
        console.error("chat-callbacks: pin failed", err);
        toast.error("Couldn’t pin this message");
      }
    },
    [agent],
  );

  /**
   * Share (row 13, feature-map): render this reply as a branded PNG card,
   * download it, and surface the prefilled caption for pasting to X /
   * LinkedIn. Best-effort — a toast, no throw, when the environment can't
   * render a canvas.
   */
  const onShare = useCallback((m: AssistantMessage) => {
    try {
      const caption = shareMessageAsCard(m.content);
      toast.success("Card downloaded — caption ready to paste", {
        description: caption, duration: 4000,
      });
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        void navigator.clipboard.writeText(caption).catch(() => undefined);
      }
    } catch (err) {
      console.error("chat-callbacks: share failed", err);
      toast.error("Couldn’t create a share card here");
    }
  }, []);

  return { onThumbsUp, onThumbsDown, onRegenerate, onEditMessage, onReadAloud, onRewind, onPin, onShare };
}
