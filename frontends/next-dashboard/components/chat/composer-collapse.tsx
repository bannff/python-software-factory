"use client";

/**
 * Row 12 (feature-map): "Collapse the message input." Puts ONLY the
 * composer away while reading a long reply (never the transcript above
 * it), leaving a labelled restore bar that reports the unsent draft's
 * first line. Off by default; the choice persists via the owner's Chat
 * preference (`ChatPreferences.collapse_message_input`).
 *
 * `CopilotChatInput` has no native collapse mode (confirmed by reading
 * its real type definitions: no `collapsed`/`hidden` prop exists) — but
 * `CopilotChatView`'s own `input` slot accepts a full replacement
 * component matching its prop shape (`SlotValue<C> = C | ... | Partial
 * <ComponentProps<C>>`), so this swaps in a restore bar in place of the
 * real input rather than hiding rendered DOM — the composer's own
 * internal state (and any in-progress IME composition) is never
 * preserved across the swap, which is fine: collapsing is a deliberate
 * "put this away" action, not a mid-keystroke pause.
 */
import { useState } from "react";
import { ChevronUp } from "lucide-react";
import { CopilotChatInput, type CopilotChatInputProps } from "@copilotkit/react-core/v2";
import { routeComposerSubmit } from "@/lib/chat/side-chat";

function firstLine(value: string | undefined): string {
  const line = (value ?? "").split("\n", 1)[0]?.trim() ?? "";
  return line || "Empty draft";
}

/** ``renderSlot`` (the SDK's own slot resolver) only forwards ITS OWN
 * generic input props (value/onChange/onSubmitMessage/...) to a
 * component-shaped slot value — it does NOT also merge in a sibling
 * props OBJECT the same way it does for a plain object slot value.
 * So ``textArea``/``sendButton``/``disclaimer``/``showDisclaimer``
 * (this app's own composer overrides, unrelated to row 12) must be
 * baked into THIS wrapper's own render of the real ``<CopilotChatInput>``
 * rather than passed alongside it at the call site — confirmed by
 * reading the SDK's ``renderSlot``/``CopilotChatView`` source directly
 * before designing this, not assumed from the type definitions alone. */
export function makeCollapsibleComposerInput(
  enabled: boolean,
  overrides: Pick<CopilotChatInputProps, "textArea" | "sendButton" | "disclaimer" | "showDisclaimer">,
  onSideCommand?: (query: string) => void,
) {
  // Row 19 (feature-map): divert `/side`·`/btw` to the side panel before the
  // message reaches the main agent. When no handler is supplied, submit is
  // untouched.
  const withSideRoute = (props: CopilotChatInputProps): CopilotChatInputProps =>
    onSideCommand
      ? {
          ...props,
          onSubmitMessage: (value: string) =>
            routeComposerSubmit(value, {
              onSide: onSideCommand,
              onSend: (v) => props.onSubmitMessage?.(v),
            }),
        }
      : props;

  if (!enabled) {
    const Plain: React.FC<CopilotChatInputProps> = (props) => (
      <CopilotChatInput {...withSideRoute(props)} {...overrides} />
    );
    Plain.displayName = "ComposerInput";
    return Plain;
  }

  const Collapsible: React.FC<CopilotChatInputProps> = (props) => {
    const [collapsed, setCollapsed] = useState(false);
    if (!collapsed) {
      return (
        <div className="relative">
          <CopilotChatInput {...withSideRoute(props)} {...overrides} />
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            aria-label="Collapse the message input"
            className="absolute -top-6 right-2 rounded-md border border-border/50 bg-card/60 px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-accent/30 hover:text-foreground"
          >
            Collapse
          </button>
        </div>
      );
    }
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        aria-label="Restore the message input"
        className="flex w-full items-center gap-2 border-t border-border/50 bg-card/40 px-3 py-2 text-left text-xs text-muted-foreground hover:bg-accent/30 hover:text-foreground"
      >
        <ChevronUp className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{firstLine(props.value)}</span>
      </button>
    );
  };
  Collapsible.displayName = "CollapsibleComposerInput";
  return Collapsible;
}
