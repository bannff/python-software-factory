/**
 * Owner-remappable keyboard shortcuts.
 *
 * A chord is stored normalized as `mod+shift+alt+<key>` ("mod" = ⌘ on macOS,
 * Ctrl elsewhere) and lives in the durable Display preference (`shortcuts`).
 * Consumers call `matchesChord(event, chord)`; the Settings panel records a
 * chord with `chordFromEvent` and shows it with `formatChord`.
 */
export interface ShortcutAction {
  id: string;
  area: string;
  label: string;
  /** Default normalized chord; `null` marks a fixed structural key that cannot be remapped. */
  defaultChord: string | null;
  /** Human-readable keys when the action is not remappable. */
  fixedKeys?: string[];
}

export const SHORTCUT_ACTIONS: readonly ShortcutAction[] = [
  { id: "command_palette", area: "Global", label: "Open or close command palette", defaultChord: "mod+k" },
  { id: "toggle_chat", area: "Global", label: "Show or hide the chat sidebar", defaultChord: "mod+j" },
  { id: "toggle_terminal", area: "Global", label: "Show or hide the Terminal dock", defaultChord: "mod+`" },
  { id: "session_rows", area: "Sessions", label: "Move between focused session rows", defaultChord: null, fixedKeys: ["↑", "↓"] },
  { id: "section_nav", area: "Settings and Agent Capabilities", label: "Select previous or next section", defaultChord: null, fixedKeys: ["←", "→"] },
  { id: "section_ends", area: "Settings and Agent Capabilities", label: "Select first or last section", defaultChord: null, fixedKeys: ["Home", "End"] },
];

const SPECIAL: Record<string, string> = {
  " ": "space", Enter: "enter", Escape: "escape", Tab: "tab",
};
const CHORD = /^(?:mod\+)?(?:shift\+)?(?:alt\+)?(?:[a-z0-9`]|enter|escape|space|tab|f[1-9]|f1[0-2])$/;

export function isChord(value: string): boolean {
  return CHORD.test(value);
}

/** Normalize a keydown into a chord, or null when it is only modifiers. */
export function chordFromEvent(event: Pick<KeyboardEvent, "key" | "metaKey" | "ctrlKey" | "shiftKey" | "altKey">): string | null {
  const raw = event.key;
  if (["Meta", "Control", "Shift", "Alt"].includes(raw)) return null;
  const key = SPECIAL[raw] ?? (raw.length === 1 ? raw.toLowerCase() : raw.toLowerCase());
  const parts = [
    event.metaKey || event.ctrlKey ? "mod" : "", event.shiftKey ? "shift" : "", event.altKey ? "alt" : "", key,
  ].filter(Boolean);
  const chord = parts.join("+");
  return isChord(chord) ? chord : null;
}

export function matchesChord(event: Pick<KeyboardEvent, "key" | "metaKey" | "ctrlKey" | "shiftKey" | "altKey">, chord: string): boolean {
  return chordFromEvent(event) === chord;
}

/** Effective chord for an action given the owner's overrides. */
export function effectiveChord(actionId: string, overrides: Record<string, string>): string | null {
  const action = SHORTCUT_ACTIONS.find((item) => item.id === actionId);
  if (!action || action.defaultChord === null) return null;
  const override = overrides[actionId];
  return override && isChord(override) ? override : action.defaultChord;
}

const MAC = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform ?? "");

export function formatChord(chord: string): string[] {
  return chord.split("+").map((part) => {
    if (part === "mod") return MAC ? "⌘" : "Ctrl";
    if (part === "shift") return "⇧";
    if (part === "alt") return MAC ? "⌥" : "Alt";
    if (part === "space") return "Space";
    return part.length === 1 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1);
  });
}
