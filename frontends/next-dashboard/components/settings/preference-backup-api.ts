import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/** Row 102 (feature-map): a complete, opaque snapshot of one owner's
 * durable UI preferences (chat/display/shortcuts/memory-mode). Passed
 * through verbatim on restore — the client never needs to know every
 * field, only that ``ui_export_preferences``'s shape is exactly what
 * ``ui_import_preferences`` accepts back. */
export type PreferenceSnapshot = Record<string, unknown>;

function record(raw: unknown): PreferenceSnapshot {
  if (!raw || typeof raw !== "object") throw new Error("Preference backup is unavailable.");
  return raw as PreferenceSnapshot;
}

export async function exportPreferences(): Promise<PreferenceSnapshot> {
  return record(unwrapToolData(await callTool("ui_export_preferences")));
}

export async function importPreferences(snapshot: PreferenceSnapshot): Promise<PreferenceSnapshot> {
  return record(unwrapToolData(await callTool("ui_import_preferences", snapshot)));
}
