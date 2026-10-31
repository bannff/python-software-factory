"use client";

/**
 * Row 13 (feature-map) — turn an assistant reply into a shareable branded
 * PNG card plus a prefilled caption for X / LinkedIn.
 *
 * Scaffold: the card is rendered client-side onto a canvas (no server, no
 * external service) and downloaded; the caption is prefilled text the owner
 * can paste. Governance (`capabilities.social_share`) and the platform
 * share-intent deep links are deliberately deferred — this ships the core
 * "make a card from a message" capability first.
 */

const CARD_WIDTH = 1200;
const CARD_HEIGHT = 630; // 1.91:1 — the standard social/OG card ratio.
const CAPTION_MAX = 260; // headroom under X's limit, leaving room for a link.

/** Plain text from an AG-UI message content (string or parts array). */
export function messageText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => (typeof part === "object" && part && "text" in part
        && typeof (part as { text?: unknown }).text === "string"
        ? (part as { text: string }).text : ""))
      .filter(Boolean).join(" ");
  }
  return "";
}

/** A prefilled caption: the message's first meaningful line, trimmed and
 * length-capped (never mid-emoji-surrogate), with an ellipsis when cut. */
export function buildShareCaption(content: unknown): string {
  const firstLine = messageText(content).trim().split(/\n+/).find((line) => line.trim()) ?? "";
  const collapsed = firstLine.replace(/\s+/g, " ").trim();
  if (collapsed.length <= CAPTION_MAX) return collapsed;
  return `${[...collapsed].slice(0, CAPTION_MAX).join("").trimEnd()}…`;
}

/** Wrap text into lines that fit ``maxWidth`` for the given 2D context. */
function wrapLines(ctx: CanvasRenderingContext2D, text: string, maxWidth: number, maxLines: number): string[] {
  const words = text.replace(/\s+/g, " ").trim().split(" ");
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (ctx.measureText(candidate).width > maxWidth && current) {
      lines.push(current);
      current = word;
      if (lines.length === maxLines - 1) break;
    } else {
      current = candidate;
    }
  }
  if (current && lines.length < maxLines) lines.push(current);
  const consumed = lines.join(" ").length;
  if (consumed < text.replace(/\s+/g, " ").trim().length && lines.length) {
    lines[lines.length - 1] = `${lines[lines.length - 1]}…`;
  }
  return lines;
}

/** Render the message onto a themed card canvas and return a PNG data URL,
 * or null when the environment has no usable 2D canvas (e.g. jsdom). */
export function renderMessageCard(content: unknown): string | null {
  if (typeof document === "undefined") return null;
  const canvas = document.createElement("canvas");
  canvas.width = CARD_WIDTH;
  canvas.height = CARD_HEIGHT;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = "#0b0b12";
  ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
  ctx.fillStyle = "#a78bfa";
  ctx.fillRect(0, 0, 8, CARD_HEIGHT);
  ctx.fillStyle = "#e5e7eb";
  ctx.font = "600 44px system-ui, sans-serif";
  wrapLines(ctx, messageText(content), CARD_WIDTH - 140, 7)
    .forEach((line, i) => ctx.fillText(line, 70, 140 + i * 62));
  ctx.fillStyle = "#8b8b9a";
  ctx.font = "500 28px system-ui, sans-serif";
  ctx.fillText("Companion-X", 70, CARD_HEIGHT - 50);
  return canvas.toDataURL("image/png");
}

/** Build the card + caption for a message and trigger a PNG download.
 * Returns the caption (for the caller to surface for pasting), or throws
 * when no card could be rendered. */
export function shareMessageAsCard(content: unknown, filename = "companion-x-card.png"): string {
  const dataUrl = renderMessageCard(content);
  if (!dataUrl) throw new Error("card rendering is unavailable here");
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = filename;
  link.click();
  return buildShareCaption(content);
}
