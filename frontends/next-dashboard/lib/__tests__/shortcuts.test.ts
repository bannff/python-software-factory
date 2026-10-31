import { describe, expect, it } from "vitest";
import { SHORTCUT_ACTIONS, chordFromEvent, effectiveChord, formatChord, isChord, matchesChord } from "../shortcuts";

const key = (k: string, mods: Partial<Pick<KeyboardEvent, "metaKey" | "ctrlKey" | "shiftKey" | "altKey">> = {}) =>
  ({ key: k, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false, ...mods });

describe("shortcut chords", () => {
  it("normalizes ⌘ and Ctrl to the same 'mod' chord in a stable modifier order", () => {
    expect(chordFromEvent(key("K", { metaKey: true }))).toBe("mod+k");
    expect(chordFromEvent(key("k", { ctrlKey: true }))).toBe("mod+k");
    expect(chordFromEvent(key("P", { ctrlKey: true, altKey: true, shiftKey: true }))).toBe("mod+shift+alt+p");
    expect(chordFromEvent(key("`", { metaKey: true }))).toBe("mod+`");
    expect(chordFromEvent(key(" ", { metaKey: true }))).toBe("mod+space");
  });

  it("ignores modifier-only presses and unsupported keys", () => {
    expect(chordFromEvent(key("Meta", { metaKey: true }))).toBeNull();
    expect(chordFromEvent(key("ArrowDown"))).toBeNull();
    expect(isChord("Cmd+K")).toBe(false);
    expect(isChord("mod+ctrl+k")).toBe(false);
  });

  it("matches events against a chord and resolves owner overrides over defaults", () => {
    expect(matchesChord(key("k", { metaKey: true }), "mod+k")).toBe(true);
    expect(matchesChord(key("k", { metaKey: true, shiftKey: true }), "mod+k")).toBe(false);
    expect(effectiveChord("command_palette", {})).toBe("mod+k");
    expect(effectiveChord("command_palette", { command_palette: "mod+shift+p" })).toBe("mod+shift+p");
    expect(effectiveChord("command_palette", { command_palette: "not a chord" })).toBe("mod+k");
    expect(effectiveChord("section_nav", { section_nav: "mod+x" })).toBeNull();
  });

  it("formats chords for display and lists every remappable default as a valid chord", () => {
    expect(formatChord("mod+shift+p").at(-1)).toBe("P");
    expect(formatChord("mod+space")).toContain("Space");
    for (const action of SHORTCUT_ACTIONS) if (action.defaultChord) expect(isChord(action.defaultChord)).toBe(true);
  });
});

describe("chord grammar parity with the backend", () => {
  it("accepts and rejects exactly the shared vectors", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const vectors = JSON.parse(readFileSync(resolve(
      __dirname, "../../../../components/ui/test/factory/ui/fixtures/shortcut_chords.json",
    ), "utf8")) as { accept: string[]; reject: string[] };
    for (const chord of vectors.accept) expect(isChord(chord), chord).toBe(true);
    for (const chord of vectors.reject) expect(isChord(chord), chord).toBe(false);
  });
});
