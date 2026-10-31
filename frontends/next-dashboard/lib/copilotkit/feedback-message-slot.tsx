"use client";

/**
 * Custom assistantMessage slot that fans out toolbar callbacks with the
 * correct AssistantMessage payload (bd-2dq6).
 *
 * Why this is needed: CopilotKit v2 1.53 documents the assistant
 * toolbar callbacks as ``(message: AssistantMessage) => void``, but the
 * runtime binds them as plain ``onClick`` handlers (see
 * CopilotChatAssistantMessage.mjs — `{ onClick: onThumbsUp }`), so the
 * handler actually receives a MouseEvent. The result is that
 * `message.id` is `undefined` when feedback is persisted to memory.
 *
 * This wrapper renders the default ``<CopilotChatAssistantMessage />``
 * but rebinds the toolbar callbacks to closures that pre-supply the
 * correct ``message``. From the consumer's perspective the original
 * documented signature `(message) => void` Just Works.
 */

import type { AssistantMessage } from "@ag-ui/core";
import { Pin, RotateCcw, Share2 } from "lucide-react";
import {
  CopilotChatAssistantMessage,
  type CopilotChatAssistantMessageProps,
} from "@copilotkit/react-core/v2";

type AssistantMessageSlotProps = CopilotChatAssistantMessageProps;

export interface AssistantMessageCallbacks {
  onThumbsUp?: (m: AssistantMessage) => void;
  onThumbsDown?: (m: AssistantMessage) => void;
  onRegenerate?: (m: AssistantMessage) => void;
  onReadAloud?: (m: AssistantMessage) => void;
  /** Row 15 (feature-map): rewind the transcript back to this message,
   * generating nothing new. Rendered via the SDK's own
   * ``additionalToolbarItems`` extension point + exported
   * ``ToolbarButton`` — no custom overlay needed, since the vendored
   * component already supports adding toolbar buttons beyond its four
   * fixed callbacks, confirmed by reading its real type definitions
   * rather than assumed from its documented props alone. */
  onRewind?: (m: AssistantMessage) => void;
  /** Row 9 (feature-map): pin/unpin this message for its session. Rendered
   * via the same ``additionalToolbarItems`` extension point as Rewind. */
  onPin?: (m: AssistantMessage) => void;
  /** Row 13 (feature-map): share this reply as a branded card + caption. */
  onShare?: (m: AssistantMessage) => void;
  /**
   * Optional override for the assistant-message MarkdownRenderer slot.
   * Used by the chat sidebar to plug in a project-themed code-block
   * renderer with syntax highlighting and a copy button (bd-ezy3).
   */
  markdownRenderer?: CopilotChatAssistantMessageProps["markdownRenderer"];
}

/**
 * Build a slot component that closes over the documented
 * (message-aware) callbacks. The component is recreated each time the
 * callbacks change so React's referential equality on the slot prop
 * stays clean.
 */
export function makeAssistantMessageSlot(callbacks: AssistantMessageCallbacks) {
  const Slot: React.FC<AssistantMessageSlotProps> = (props) => {
    const m = props.message;
    return (
      <CopilotChatAssistantMessage
        {...props}
        markdownRenderer={callbacks.markdownRenderer ?? props.markdownRenderer}
        onThumbsUp={callbacks.onThumbsUp ? () => callbacks.onThumbsUp!(m) : undefined}
        onThumbsDown={callbacks.onThumbsDown ? () => callbacks.onThumbsDown!(m) : undefined}
        onRegenerate={callbacks.onRegenerate ? () => callbacks.onRegenerate!(m) : undefined}
        onReadAloud={callbacks.onReadAloud ? () => callbacks.onReadAloud!(m) : undefined}
        additionalToolbarItems={(callbacks.onRewind || callbacks.onPin || callbacks.onShare) ? (
          <>
            {callbacks.onRewind && (
              <CopilotChatAssistantMessage.ToolbarButton
                title="Rewind to this point"
                onClick={() => callbacks.onRewind!(m)}
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </CopilotChatAssistantMessage.ToolbarButton>
            )}
            {callbacks.onPin && (
              <CopilotChatAssistantMessage.ToolbarButton
                title="Pin this message"
                onClick={() => callbacks.onPin!(m)}
              >
                <Pin className="h-3.5 w-3.5" />
              </CopilotChatAssistantMessage.ToolbarButton>
            )}
            {callbacks.onShare && (
              <CopilotChatAssistantMessage.ToolbarButton
                title="Share as image"
                onClick={() => callbacks.onShare!(m)}
              >
                <Share2 className="h-3.5 w-3.5" />
              </CopilotChatAssistantMessage.ToolbarButton>
            )}
          </>
        ) : undefined}
      />
    );
  };
  Slot.displayName = "AssistantMessageWithFeedback";
  return Slot;
}


import {
  CopilotChatUserMessage,
  type CopilotChatUserMessageProps,
} from "@copilotkit/react-core/v2";
import type { UserMessage } from "@ag-ui/core";
import type { SteeredMessage } from "./steer-delivery";
import { SteerStatus } from "./steer-status";

export interface UserMessageCallbacks {
  onEditMessage?: (props: { message: UserMessage }) => void;
}

export function makeUserMessageSlot(callbacks: UserMessageCallbacks) {
  const Slot: React.FC<CopilotChatUserMessageProps> = (props) => {
    const delivery = (props.message as SteeredMessage).steerDelivery;
    return (
      <div className="relative">
        {delivery && <SteerStatus state={delivery.state} />}
        <CopilotChatUserMessage
          {...props}
          onEditMessage={
            callbacks.onEditMessage
              ? () => callbacks.onEditMessage!({ message: props.message })
              : undefined
          }
        />
      </div>
    );
  };
  Slot.displayName = "UserMessageWithEdit";
  return Slot;
}
