"use client";

/**
 * <StopAwareSendButton /> — drop-in replacement for the v2 default
 * `<CopilotChatInput.SendButton />` slot that adds a discoverable
 * "Stop generating" tooltip when the agent is mid-stream (bd-01wh).
 *
 * NATIVE PATTERN — no bespoke abort flow:
 *   - `<CopilotChat>` already wires `onStop` to its
 *     `CopilotChatInput`, which morphs the send button into a Square
 *     stop button when `agent.isRunning && hasMessages`. The morph
 *     ships the Square via the slot's `children` prop (see v2 source
 *     CopilotChatInput.tsx — `children: isProcessing && canStop ? <Square /> : undefined`).
 *   - All we add is a tooltip on top so the affordance is
 *     discoverable. The button's onClick still calls v2's
 *     `stopCurrentRun → copilotkit.stopAgent({ agent }) → agent.abortRun()`,
 *     which terminates the in-flight AG-UI run. The chat adapter on
 *     the backend already cancels on disconnect (bd-anci) — so onStop
 *     is wired all the way through to the LangChain/LangGraph runtime.
 *
 * Detection of stop-mode: the v2 source passes a `<Square />` child
 * only when running; otherwise it lets the default button render its
 * own ArrowUp icon. We mirror that signal — `children` defined ⇒
 * stop-mode ⇒ "Stop generating" tooltip; otherwise ⇒ "Send message".
 *
 * Wired via:
 *   <CopilotChat input={{ sendButton: StopAwareSendButton }} />
 */

import type { ButtonHTMLAttributes } from "react";
import { CopilotChatInput } from "@copilotkit/react-core/v2";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function StopAwareSendButton(
  props: ButtonHTMLAttributes<HTMLButtonElement>,
) {
  const { ready, status } = useMcpConnection();
  const stopMode = props.children !== undefined;
  const label = stopMode
    ? "Stop generating"
    : ready
      ? "Send message"
      : status === "error" ? "Tools unavailable" : "Connecting to tools";
  const disabled = stopMode ? props.disabled : props.disabled || !ready;
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          {/*
            Render the v2 default SendButton verbatim. The default
            already wraps a `<Button>` inside a small right-margin div
            and forwards `onClick` / `disabled` / `children`, so
            plugging it back in keeps the visual identical to upstream.
          */}
          <CopilotChatInput.SendButton {...props} disabled={disabled} aria-label={label} />
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          {label}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
