import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
export interface NotificationChannel { id: string; type: string; name: string; enabled: boolean; }
export type NotificationPriority = "passive" | "default" | "critical";
export interface NotificationPreferences {
  globalMuted: boolean;
  mutedKinds: string[];
  priorityOverrides: Record<string, NotificationPriority>;
  revision: number;
}
export async function listNotificationChannels(): Promise<NotificationChannel[]> {
  const data = unwrapToolData(await callTool("notification_get_channel_registry")) as { channels?: unknown };
  if (!Array.isArray(data?.channels)) throw new Error("Notification channels unavailable.");
  return data.channels.flatMap((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const value = raw as Record<string, unknown>;
    if (typeof value.id !== "string") return [];
    return [{ id: value.id, type: typeof value.type === "string" ? value.type : "unknown",
      name: typeof value.name === "string" ? value.name : value.id, enabled: value.enabled !== false }];
  });
}

function parsePreferences(raw: unknown): NotificationPreferences {
  if (!raw || typeof raw !== "object") throw new Error("Notification preferences unavailable.");
  const value = raw as Record<string, unknown>;
  const priorities = value.priority_overrides;
  if (typeof value.global_muted !== "boolean" || !Array.isArray(value.muted_kinds)
      || !priorities || typeof priorities !== "object" || Array.isArray(priorities)
      || typeof value.revision !== "number") throw new Error("Notification preferences unavailable.");
  if (!value.muted_kinds.every((kind) => typeof kind === "string"))
    throw new Error("Notification preferences unavailable.");
  const priorityOverrides: Record<string, NotificationPriority> = {};
  for (const [kind, priority] of Object.entries(priorities)) {
    if (priority !== "passive" && priority !== "default" && priority !== "critical")
      throw new Error("Notification preferences unavailable.");
    priorityOverrides[kind] = priority;
  }
  return { globalMuted: value.global_muted, mutedKinds: value.muted_kinds as string[],
    priorityOverrides, revision: value.revision };
}

export async function getNotificationPreferences(): Promise<NotificationPreferences> {
  return parsePreferences(unwrapToolData(await callTool("notification_get_preferences")));
}

export async function updateNotificationPreferences(
  preferences: NotificationPreferences,
): Promise<NotificationPreferences> {
  return parsePreferences(unwrapToolData(await callTool("notification_update_preferences", {
    global_muted: preferences.globalMuted,
    muted_kinds: preferences.mutedKinds,
    priority_overrides: preferences.priorityOverrides,
    expected_revision: preferences.revision,
  })));
}
