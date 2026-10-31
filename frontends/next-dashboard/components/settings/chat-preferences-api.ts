import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export type DefaultMemoryMode = "persistent" | "incognito" | "temporary";

export interface ChatPreferences {
  plainDiffs: boolean;
  hiddenModels: string[];
  defaultMemoryMode: DefaultMemoryMode;
  collapseMessageInput: boolean;
  pinLatestPrompt: boolean;
  revision: number;
}

const MEMORY_MODES = new Set<string>(["persistent", "incognito", "temporary"]);

function parse(raw: unknown): ChatPreferences {
  if (!raw || typeof raw !== "object") throw new Error("Chat preferences are unavailable.");
  const value = raw as Record<string, unknown>;
  if (typeof value.plain_diffs !== "boolean" || !Array.isArray(value.hidden_models)
      || typeof value.revision !== "number") throw new Error("Chat preferences are unavailable.");
  const hiddenModels = value.hidden_models.filter((item): item is string => typeof item === "string");
  if (hiddenModels.length !== value.hidden_models.length) throw new Error("Chat preferences are unavailable.");
  const rawMode = value.default_memory_mode;
  const defaultMemoryMode: DefaultMemoryMode =
    typeof rawMode === "string" && MEMORY_MODES.has(rawMode) ? rawMode as DefaultMemoryMode : "persistent";
  const collapseMessageInput = value.collapse_message_input === true;
  return { plainDiffs: value.plain_diffs, hiddenModels, defaultMemoryMode, collapseMessageInput, pinLatestPrompt: value.pin_latest_prompt === true, revision: value.revision };
}

export async function getChatPreferences(): Promise<ChatPreferences> {
  return parse(unwrapToolData(await callTool("ui_get_chat_preferences")));
}

export async function updateChatPreferences(value: ChatPreferences): Promise<ChatPreferences> {
  return parse(unwrapToolData(await callTool("ui_update_chat_preferences", {
    plain_diffs: value.plainDiffs,
    hidden_models: value.hiddenModels,
    default_memory_mode: value.defaultMemoryMode,
    collapse_message_input: value.collapseMessageInput,
    pin_latest_prompt: value.pinLatestPrompt,
    expected_revision: value.revision,
  })));
}
