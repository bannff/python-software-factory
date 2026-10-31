"use client";

/**
 * <ChatDisclaimer /> — replacement for the v2 default disclaimer slot
 * (bd-js4a / D1).
 *
 * The default `<CopilotChatInput.Disclaimer />` inherits the chat
 * surface's prose styles, which renders the "AI can make mistakes"
 * line as white 16px text — way too loud for a footer. Per UX audit
 * `fcc20db2`, drop it to muted 10px and centre it, matching the
 * proportions used by ChatGPT / Claude / Copilot.
 *
 * Implementation note: the chat sidebar lives under `[data-copilotkit]`
 * which redefines `--muted-foreground` and `--foreground` from the v2
 * stylesheet. Project Tailwind utilities like `text-muted-foreground`
 * use `hsl(var(--muted-foreground))` which fails when the variable
 * holds an `oklch(...)` value, so the text falls back to the inherited
 * foreground (near-white). We render with an inline RGBA token instead
 * so the disclaimer reads as a proper muted footer in both light and
 * dark themes.
 *
 * Rendered via `<CopilotChat input={{ disclaimer: ChatDisclaimer }}>`.
 */

import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const DEFAULT_TEXT =
  "AI can make mistakes. Verify important details. Press Enter again or click ◼ to stop.";

const DISCLAIMER_STYLE = {
  // Slate-400 @ 60% — readable, not loud, theme-agnostic.
  color: "rgba(148, 163, 184, 0.6)",
};

interface ChatDisclaimerProps extends HTMLAttributes<HTMLDivElement> {
  text?: string;
}

export function ChatDisclaimer({ text, className, style, ...rest }: ChatDisclaimerProps) {
  return (
    <div
      {...rest}
      style={{ ...DISCLAIMER_STYLE, ...style }}
      className={cn(
        "mx-auto max-w-3xl px-4 py-2 text-center text-[10px] leading-tight",
        className,
      )}
    >
      {text ?? DEFAULT_TEXT}
    </div>
  );
}
