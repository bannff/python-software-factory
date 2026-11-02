import type { Hook, HookFiring } from "./hooks-api";

/** The bus records events, not per-subscription dispatches, so this is the
 * event type's history. A wildcard pattern is never a literal event type,
 * and a disabled hook is not receiving the events at all. */
export function hasEventHistory(hook: Hook): boolean {
  return hook.enabled && !hook.eventType.includes("*");
}

export function eventHistoryLabel(hook: Hook, recent: HookFiring[]): string | null {
  if (!hasEventHistory(hook)) return null;
  return recent.length === 0
    ? "No recent events of this type."
    : `Event last seen ${new Date(recent[0].timestamp).toLocaleString()}`;
}
