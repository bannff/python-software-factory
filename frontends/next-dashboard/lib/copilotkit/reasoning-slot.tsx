"use client";

/**
 * Capped-height wrapper around the v2 default
 * <CopilotChatReasoningMessage /> so the "Thinking…" panel never
 * pushes the assistant's actual response below the fold (bd-k8xk).
 *
 * Wired via the same `messageView` slot the chat sidebar already uses
 * for assistantMessage / userMessage. The default panel does not
 * expose a `maxHeight` prop (verified against
 * components/chat/CopilotChatReasoningMessage.d.mts on @copilotkitnext/react),
 * so the wrapper-div pattern is the SDK-native shape: render the
 * default panel inside an `overflow-y-auto` container with a hard cap.
 *
 * 240px = roughly 12 lines of reasoning copy at the v2 base size.
 * Chosen so a long thinking trace stays visible (scrollable) without
 * eating the response viewport.
 */

import {
  CopilotChatReasoningMessage,
  type CopilotChatReasoningMessageProps,
} from "@copilotkit/react-core/v2";

export function ReasoningSlot(props: CopilotChatReasoningMessageProps) {
  return (
    <div className="max-h-60 overflow-y-auto">
      <CopilotChatReasoningMessage {...props} />
    </div>
  );
}
