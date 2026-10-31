"use client";

import { type RefObject, useCallback, useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";

/**
 * Row 19 (feature-map) — "Ask about this" on selected assistant text.
 *
 * When the user selects text inside the chat transcript, a small floating
 * button offers to open the Side panel seeded with that span (the third
 * entry point alongside the `/side`·`/btw` composer command and the Side
 * tab's own input). The pure prompt-building lives in `lib/chat/side-chat.ts`
 * (`buildAskAboutPrompt`); this is the selection glue + affordance.
 */

interface Anchor { text: string; top: number; left: number }

/** Presentational floating button — pure, positioned by its parent. */
export function AskAboutThisButton({ top, left, onClick }: { top: number; left: number; onClick: () => void }) {
  return (
    <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={onClick}
      aria-label="Ask about this on the side"
      style={{ top, left }}
      className="absolute z-30 flex items-center gap-1 rounded-md border border-border/60 bg-card px-2 py-1 text-[11px] shadow-lg hover:bg-accent/40">
      <MessagesSquare className="h-3 w-3" /> Ask about this
    </button>
  );
}

/** Track a text selection anchored inside `containerRef`. Thin DOM glue. */
export function useSelectionAnchor(containerRef: RefObject<HTMLElement | null>): {
  anchor: Anchor | null;
  clear: () => void;
} {
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const clear = useCallback(() => setAnchor(null), []);

  useEffect(() => {
    const onMouseUp = () => {
      const container = containerRef.current;
      const selection = typeof window !== "undefined" ? window.getSelection() : null;
      if (!container || !selection || selection.isCollapsed) { setAnchor(null); return; }
      const text = selection.toString().trim();
      if (!text || !container.contains(selection.anchorNode)) { setAnchor(null); return; }
      const range = selection.getRangeAt(0).getBoundingClientRect();
      const box = container.getBoundingClientRect();
      setAnchor({
        text,
        top: Math.max(range.bottom - box.top + 4, 0),
        left: Math.max(Math.min(range.left - box.left, box.width - 120), 0),
      });
    };
    document.addEventListener("mouseup", onMouseUp);
    return () => document.removeEventListener("mouseup", onMouseUp);
  }, [containerRef]);

  return { anchor, clear };
}

/** The overlay wired over the transcript region. */
export function AskAboutThisOverlay({ containerRef, onAsk }: {
  containerRef: RefObject<HTMLElement | null>;
  onAsk: (text: string) => void;
}) {
  const { anchor, clear } = useSelectionAnchor(containerRef);
  if (!anchor) return null;
  return (
    <AskAboutThisButton top={anchor.top} left={anchor.left}
      onClick={() => { onAsk(anchor.text); clear(); }} />
  );
}
