"use client";

import { useEffect, useRef } from "react";
import type { Message } from "@ag-ui/core";
import { generateSessionTitle } from "@/components/operations/sessions/session-actions";
import type { SessionSummary } from "./use-session-list";

const DEFAULT_TITLE = "New session";
const FALLBACK_TITLE = "New chat";
const EXCERPT_MESSAGE_CAP = 4;
const EXCERPT_CHAR_CAP = 2000;

/**
 * Row 17 (feature-map) — automatic session title generation, fired once
 * per session right after the first assistant reply lands.
 *
 * Two distinct mechanical-title shapes exist today, both correctly treated
 * as "not yet a real generated title" (found via live verification on the
 * smoke instance, not assumed): (1) the literal `"New session"` placeholder
 * `start-default-crew-session.ts` sets when a session is created via the
 * deck's own **New session** button; (2) the FAR more common real path —
 * `session_steering.py::ensure_thread` sets the title to the raw first
 * line of the user's own first message (`request.prompt...splitlines()[0]`,
 * falling back to `"New chat"`), which is what the Welcome-flow chat
 * (typing directly, no deck button) actually uses. Both are mechanical
 * placeholders, not a real title — this hook only skips firing once the
 * title is something ELSE (a prior real generation, or a manual rename).
 */
export function useAutoTitle(
  session: SessionSummary | undefined, messages: Message[], isRunning: boolean,
  onGenerated?: () => void,
): void {
  const firedFor = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!session || isRunning) return;
    if (!isMechanicalTitle(session, messages)) return;
    if (firedFor.current.has(session.session_id)) return;
    const hasAssistantReply = messages.some((message) => message.role === "assistant");
    if (!hasAssistantReply) return;

    firedFor.current.add(session.session_id);
    const excerpt = messages
      .slice(0, EXCERPT_MESSAGE_CAP)
      .map((message) => `${message.role}: ${flatten(message.content)}`)
      .join("\n")
      .slice(0, EXCERPT_CHAR_CAP);
    if (!excerpt.trim()) return;

    void generateSessionTitle(session.session_id, excerpt, session.revision)
      .then(() => onGenerated?.())
      .catch(() => {
        // Fire-and-forget: leave the placeholder title in place on failure.
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id, session?.title, session?.revision, isRunning, messages.length]);
}

/** True when ``session.title`` is still a mechanical placeholder rather
 * than a real generated (or manually chosen) title — either the literal
 * deck-created default, or the raw first line of the user's own first
 * message (the ``ensure_thread`` fallback the common Welcome-flow chat
 * actually uses). */
function isMechanicalTitle(session: SessionSummary, messages: Message[]): boolean {
  if (session.title === DEFAULT_TITLE || session.title === FALLBACK_TITLE) return true;
  const firstUser = messages.find((message) => message.role === "user");
  if (!firstUser) return false;
  const firstLine = flatten(firstUser.content).trim().split("\n")[0]?.slice(0, 200) ?? "";
  return firstLine.length > 0 && session.title === firstLine;
}

function flatten(content: unknown): string {
  return typeof content === "string" ? content : "";
}
