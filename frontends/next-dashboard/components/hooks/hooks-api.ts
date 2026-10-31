import { callTool, listTools } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Real, currently-firing agent lifecycle event types (grep-verified against
 * `events_publish(event_type=...)` call sites across the agent/workflow/
 * memory bricks — not an invented taxonomy). A hook subscribes to one of
 * these; the underlying event-bus dispatch (`dispatch.py`'s generic
 * fallback) already treats any non-reserved handler name as an MCP tool
 * to invoke, so "run this tool on this event" works today with zero new
 * backend plumbing — this file just gives it an honest picker instead of
 * free-text "Event pattern" / "Handler" fields.
 */
export const AGENT_LIFECYCLE_EVENTS = [
  { value: "system.run_started", label: "Agent run starts" },
  { value: "system.run_cancelled", label: "Agent run is cancelled" },
  { value: "workflow.failed", label: "Workflow run fails" },
  { value: "user.approved", label: "A pending approval is granted" },
  { value: "memory.store", label: "A memory is stored" },
  { value: "learning.applied", label: "A learning is applied" },
] as const;

export interface Hook {
  id: string;
  eventType: string;
  tool: string;
  description: string;
  enabled: boolean;
}

function row(raw: unknown): Hook | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.id !== "string" || typeof value.event_type !== "string"
      || typeof value.handler !== "string") return null;
  return {
    id: value.id, eventType: value.event_type, tool: value.handler,
    description: typeof value.description === "string" ? value.description : "",
    enabled: value.enabled !== false,
  };
}

export async function listHooks(): Promise<Hook[]> {
  const data = unwrapToolData(await callTool("events_get_subscription_registry")) as
    { subscriptions?: unknown };
  return Array.isArray(data?.subscriptions)
    ? data.subscriptions.map(row).filter((value): value is Hook => value !== null)
    : [];
}

export async function hookAuthoringAvailable(): Promise<boolean> {
  return (await listTools()).tools.includes("events_authoring_upsert_subscription");
}

export async function listInvocableTools(): Promise<string[]> {
  return (await listTools()).tools.filter((name) => !name.startsWith("events_")).sort();
}

export async function saveHook(hook: Hook): Promise<void> {
  const result = unwrapToolData(await callTool("events_authoring_upsert_subscription", {
    subscription_id: hook.id,
    subscription_data: {
      id: hook.id, event_type: hook.eventType, handler: hook.tool,
      description: hook.description, enabled: hook.enabled,
      priority: 0, filters: {},
    },
    dry_run: false,
  })) as { ok?: boolean; error?: string };
  if (result?.ok !== true) throw new Error(result?.error || "Hook was not saved.");
}

export async function deleteHook(id: string): Promise<void> {
  const result = unwrapToolData(await callTool("events_authoring_delete_subscription", {
    subscription_id: id,
  })) as { ok?: boolean; error?: string };
  if (result?.ok !== true) throw new Error(result?.error || "Hook was not deleted.");
}

export interface HookFiring {
  eventId: string;
  timestamp: string;
}

export async function listRecentFirings(eventType: string): Promise<HookFiring[]> {
  const data = unwrapToolData(
    await callTool("events_list_history", { event_type: eventType, limit: 10 }),
  ) as { entries?: unknown };
  if (!Array.isArray(data?.entries)) return [];
  return data.entries.flatMap((raw): HookFiring[] => {
    if (!raw || typeof raw !== "object") return [];
    const value = raw as Record<string, unknown>;
    return typeof value.event_id === "string" && typeof value.timestamp === "string"
      ? [{ eventId: value.event_id, timestamp: value.timestamp }] : [];
  });
}
