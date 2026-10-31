/**
 * Row 19 (feature-map) — Side chat seam.
 *
 * Pure helpers for the side-chat entry points (upstream's
 * `chat-core/composer/selectionActions.ts`): the `/side` and `/btw` composer
 * commands, and the "Ask about this" action on selected assistant text. Kept
 * pure and framework-free so the composer, split-view panes, and Members
 * threads can all share one seam and it stays fully unit-testable.
 *
 * This module is the routing/seeding layer only. Executing a side turn —
 * running read-only lookups (file reads, searches, fetches, read-only shell)
 * WITHOUT approval while REFUSING changes — is the deferred backend half
 * (`handlers/side.py` + a read-only tool-approval policy).
 */

const SIDE_PREFIXES = ["/side", "/btw"] as const;

export interface SideCommand {
  /** True when the input is a side-chat command (`/side …` or `/btw …`). */
  isSide: boolean;
  /** The query with the command prefix stripped (empty just opens the panel). */
  query: string;
}

/** Detect and strip a leading `/side` or `/btw` command from composer input. */
export function parseSideCommand(input: string): SideCommand {
  const trimmed = input.trimStart();
  for (const prefix of SIDE_PREFIXES) {
    if (trimmed === prefix || trimmed.toLowerCase().startsWith(`${prefix} `)) {
      return { isSide: true, query: trimmed.slice(prefix.length).trim() };
    }
  }
  return { isSide: false, query: input };
}

/** Build a seeded side query from a selected span ("Ask about this"). */
export function buildAskAboutPrompt(selectedText: string): string {
  const clean = selectedText.replace(/\s+/g, " ").trim();
  if (!clean) return "";
  const excerpt = clean.length > 500 ? `${clean.slice(0, 500)}…` : clean;
  return `About this: "${excerpt}"`;
}

/**
 * Route a composer submission: a `/side`·`/btw` command is diverted to the
 * side panel (`onSide`, with the prefix stripped) and NOT sent to the main
 * agent; anything else is sent normally (`onSend`). Pure so the composer
 * wrapper stays a thin adapter over this decision.
 */
export function routeComposerSubmit(
  value: string,
  handlers: { onSide: (query: string) => void; onSend: (value: string) => void | Promise<void> },
): "side" | "send" {
  const cmd = parseSideCommand(value);
  if (cmd.isSide) {
    handlers.onSide(cmd.query);
    return "side";
  }
  void handlers.onSend(value);
  return "send";
}
