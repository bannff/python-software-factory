"use client";

/**
 * Row 11 (feature-map) — Turn navigation minimap.
 *
 * A proportional, non-scrolling rail of markers in the transcript's left
 * gutter, one per loaded user turn. Hovering previews the prompt; clicking
 * jumps the transcript to that turn (proportional scroll — the spec's own
 * "proportional rail" model, so no fragile per-message DOM anchoring).
 * Desktop-only via a `hidden md:flex` gate; appears only with ≥ 2 turns.
 *
 * Scaffold: proportional jump + hover preview shipped; the richer upstream
 * behaviors (on-screen-turn highlight, arrow-key nav, dimmed "older history"
 * end-cap) are deferred.
 */

import type { Message } from "@ag-ui/core";

export interface Turn {
  id: string;
  preview: string;
}

/** Extract one navigable turn per user message with non-empty content. */
export function turnsFromMessages(messages: Message[]): Turn[] {
  const turns: Turn[] = [];
  for (const message of messages) {
    if (message.role !== "user") continue;
    const content = (message as { content?: unknown }).content;
    const text = typeof content === "string"
      ? content
      : Array.isArray(content)
        ? content.map((p) => (typeof p === "object" && p && "text" in p
            && typeof (p as { text?: unknown }).text === "string"
            ? (p as { text: string }).text : "")).filter(Boolean).join(" ")
        : "";
    const preview = text.replace(/\s+/g, " ").trim();
    if (preview) turns.push({ id: message.id, preview: preview.slice(0, 140) });
  }
  return turns;
}

export function TurnMinimap({ turns, onJump }: {
  turns: Turn[];
  onJump: (index: number) => void;
}) {
  if (turns.length < 2) return null;
  return (
    <div
      aria-label="Turn navigation"
      className="pointer-events-none absolute left-0 top-0 z-10 hidden h-full w-6 flex-col items-center justify-start gap-1 py-4 md:flex"
    >
      {turns.map((turn, index) => (
        <button
          key={turn.id}
          type="button"
          aria-label={`Jump to turn ${index + 1}: ${turn.preview}`}
          title={turn.preview}
          onClick={() => onJump(index)}
          className="pointer-events-auto group relative h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/40 transition-all hover:h-2 hover:w-2 hover:bg-violet-400"
        >
          <span className="pointer-events-none absolute left-4 top-1/2 hidden max-w-[240px] -translate-y-1/2 truncate rounded-md border border-border/60 bg-popover px-2 py-1 text-[10px] text-popover-foreground shadow group-hover:block">
            {turn.preview}
          </span>
        </button>
      ))}
    </div>
  );
}
