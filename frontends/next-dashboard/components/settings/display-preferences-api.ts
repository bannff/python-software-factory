import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
export type DisplayTheme = "system" | "dark" | "light";
export type DisplayDensity = "comfortable" | "compact";
/** BCP-47 tags offered in the picker; the server accepts any well-formed tag. */
export const DISPLAY_LANGUAGES: ReadonlyArray<{ tag: string; label: string }> = [
  { tag: "en", label: "English" }, { tag: "en-GB", label: "English (UK)" }, { tag: "es", label: "Español" },
  { tag: "fr", label: "Français" }, { tag: "de", label: "Deutsch" }, { tag: "pt-BR", label: "Português (Brasil)" },
  { tag: "it", label: "Italiano" }, { tag: "nl", label: "Nederlands" }, { tag: "ja", label: "日本語" },
  { tag: "ko", label: "한국어" }, { tag: "zh-CN", label: "中文 (简体)" }, { tag: "hi", label: "हिन्दी" },
];
export interface DisplayPreferences {
  theme: DisplayTheme;
  terminalFontSize: number;
  terminalShell: string | null;
  terminalCompletionEnabled: boolean;
  density: DisplayDensity;
  language: string;
  /** Owner overrides: action id → normalized chord (see lib/shortcuts). */
  shortcuts: Record<string, string>;
  revision: number;
}
function parse(raw: unknown): DisplayPreferences {
  if (!raw || typeof raw !== "object") throw new Error("Display preferences unavailable.");
  const value = raw as Record<string, unknown>;
  if (!["system", "dark", "light"].includes(String(value.theme))
      || typeof value.terminal_font_size !== "number" || typeof value.revision !== "number"
      || (value.terminal_shell !== null && typeof value.terminal_shell !== "string")
      || typeof value.terminal_completion_enabled !== "boolean"
      || !["comfortable", "compact"].includes(String(value.density))
      || typeof value.language !== "string" || !value.shortcuts || typeof value.shortcuts !== "object") {
    throw new Error("Display preferences unavailable.");
  }
  return {
    theme: value.theme as DisplayTheme, terminalFontSize: value.terminal_font_size,
    terminalShell: (value.terminal_shell as string | null) ?? null,
    terminalCompletionEnabled: value.terminal_completion_enabled,
    density: value.density as DisplayDensity, language: value.language,
    shortcuts: Object.fromEntries(Object.entries(value.shortcuts as Record<string, unknown>)
      .filter((entry): entry is [string, string] => typeof entry[1] === "string")),
    revision: value.revision,
  };
}
export async function getDisplayPreferences(): Promise<DisplayPreferences> {
  return parse(unwrapToolData(await callTool("ui_get_display_preferences")));
}
export async function updateDisplayPreferences(value: DisplayPreferences): Promise<DisplayPreferences> {
  return parse(unwrapToolData(await callTool("ui_update_display_preferences", {
    theme: value.theme, terminal_font_size: value.terminalFontSize,
    terminal_shell: value.terminalShell, terminal_completion_enabled: value.terminalCompletionEnabled,
    density: value.density, language: value.language, shortcuts: value.shortcuts,
    expected_revision: value.revision,
  })));
}
