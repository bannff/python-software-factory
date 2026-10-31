"use client";

import type { Ref, TextareaHTMLAttributes } from "react";
import { CopilotChatInput } from "@copilotkit/react-core/v2";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";

type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  ref?: Ref<HTMLTextAreaElement>;
};

/**
 * Plain function component on purpose. `CopilotChat` deep-merges its props
 * with `ts-deepmerge` on every render; a `forwardRef` slot is an object and
 * gets cloned into a fresh component type each render, remounting the
 * textarea per keystroke (caret → 0, text typed backwards). Functions are
 * preserved by the merge, and React 19 delivers `ref` as a regular prop.
 * The export is typed as the default slot so `CopilotChat`'s `SlotValue`
 * accepts it; the cast is type-only and does not change the runtime shape.
 */
function McpReadyTextAreaImpl(props: TextAreaProps) {
  const { ready, status } = useMcpConnection();
  const placeholder = ready
    ? props.placeholder
    : status === "error"
      ? "Tools unavailable — retry connection"
      : "Connecting to tools…";
  return <CopilotChatInput.TextArea {...props}
    disabled={props.disabled || !ready} placeholder={placeholder}
    aria-describedby="mcp-connection-status" />;
}

export const McpReadyTextArea =
  McpReadyTextAreaImpl as unknown as typeof CopilotChatInput.TextArea;

export function McpConnectionNotice() {
  const { status, error, retry } = useMcpConnection();
  if (status === "connected") return null;
  const failed = status === "error";
  return (
    <div id="mcp-connection-status" role={failed ? "alert" : "status"}
      aria-live="polite"
      className="flex min-h-7 items-center justify-center gap-2 border-b border-border/30 px-3 text-[10px] text-muted-foreground">
      <span>{failed ? "Tools unavailable." : "Connecting to tools…"}</span>
      {failed && error && <span className="min-w-0 truncate" title={error}>{error}</span>}
      {failed && <button type="button" onClick={retry}
        className="font-medium text-violet-400 hover:text-violet-300">Retry</button>}
    </div>
  );
}
