import { AGENT_LIFECYCLE_EVENTS } from "./hooks-api";

function sentence(code: string): string {
  const words = code.replace(/[._]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Readable label for an event type. Curated labels win; any other code is
 * humanized rather than shown raw. Callers keep the raw code in a tooltip. */
export function eventLabel(eventType: string): string {
  const known = AGENT_LIFECYCLE_EVENTS.find((option) => option.value === eventType);
  if (known) return known.label;
  if (eventType.startsWith("*.")) return `Any ${eventType.slice(2).replace(/[._]+/g, " ")} event`;
  return sentence(eventType);
}

/** Platform subscriptions store handlers as `mcp:<tool>`; the prefix is
 * transport detail, so authored and platform rows read the same. */
export function toolLabel(handler: string): string {
  return handler.startsWith("mcp:") ? handler.slice("mcp:".length) : handler;
}
