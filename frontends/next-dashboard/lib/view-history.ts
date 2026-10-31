import type { CanvasViewId } from "@/lib/types";

/**
 * Row 28 (feature-map) — Back / Forward over the workbench's own view
 * history. Companion-X navigates by switching canvas views (not URL
 * routes), so the "history" is a stack of visited views with a cursor,
 * exactly like a browser's session history: navigating forward truncates
 * any forward entries, and Back/Forward move the cursor without recording.
 *
 * Pure and self-contained so the semantics are fully unit-tested; the
 * workbench hook drives the actual view from ``currentView``.
 */

export interface ViewHistory {
  stack: CanvasViewId[];
  pos: number;
}

const MAX_ENTRIES = 50;

export function initHistory(view: CanvasViewId): ViewHistory {
  return { stack: [view], pos: 0 };
}

/** Record a forward navigation: drop any forward entries, append, advance.
 * A no-op (same reference) when the view is already current, so an
 * idempotent re-navigation never bloats the stack. */
export function pushView(history: ViewHistory, view: CanvasViewId): ViewHistory {
  if (history.stack[history.pos] === view) return history;
  const trimmed = history.stack.slice(0, history.pos + 1);
  trimmed.push(view);
  const stack = trimmed.length > MAX_ENTRIES ? trimmed.slice(trimmed.length - MAX_ENTRIES) : trimmed;
  return { stack, pos: stack.length - 1 };
}

export function canBack(history: ViewHistory): boolean {
  return history.pos > 0;
}

export function canForward(history: ViewHistory): boolean {
  return history.pos < history.stack.length - 1;
}

export function stepBack(history: ViewHistory): ViewHistory {
  return canBack(history) ? { ...history, pos: history.pos - 1 } : history;
}

export function stepForward(history: ViewHistory): ViewHistory {
  return canForward(history) ? { ...history, pos: history.pos + 1 } : history;
}

export function currentView(history: ViewHistory): CanvasViewId {
  return history.stack[history.pos];
}
