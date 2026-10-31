"use client";

import { Pin } from "lucide-react";
import type { Message } from "@ag-ui/core";

/** Row 10 (feature-map): the most recent user prompt's plain text, or "" if
 * this thread has no user message yet. Scans from the end so the "current
 * turn's own prompt" is found even while the assistant reply is streaming
 * as the last message. AG-UI content may be a string or a parts array. */
export function latestUserPrompt(messages: Message[]): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message.role !== "user") continue;
    const content = (message as { content?: unknown }).content;
    if (typeof content === "string") return content.trim();
    if (Array.isArray(content)) {
      return content
        .map((part) => (typeof part === "object" && part && "text" in part
          && typeof (part as { text?: unknown }).text === "string"
          ? (part as { text: string }).text : ""))
        .filter(Boolean).join(" ").trim();
    }
    return "";
  }
  return "";
}

/**
 * Row 10 — a sticky banner that keeps the current turn's prompt visible at
 * the top of the chat while a long reply scrolls beneath it. Pure and
 * presentational: the sidebar computes ``prompt`` from the live agent
 * messages and only renders this when the "Pin the latest turn" preference
 * is on. Renders nothing when there is no prompt to show.
 */
export function PinnedPromptBanner({ prompt }: { prompt: string | null }) {
  if (!prompt) return null;
  return (
    <div
      aria-label="Pinned prompt"
      className="sticky top-0 z-10 flex items-center gap-2 border-b border-border/40 bg-card/80 px-3 py-1.5 text-xs text-muted-foreground backdrop-blur"
    >
      <Pin className="h-3 w-3 shrink-0 text-violet-400" />
      <span className="truncate" title={prompt}>{prompt}</span>
    </div>
  );
}
