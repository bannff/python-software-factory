import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Tailwind v4's default `dark:` follows the OS setting. The app themes with
// next-themes' `.dark` class, so without this override every `dark:` utility
// (e.g. the entity pills) is wrong whenever the app and the OS disagree.
describe("dark: variant", () => {
  it("follows the app's .dark class, not prefers-color-scheme", () => {
    const css = readFileSync(resolve(process.cwd(), "../shared-renderer/src/theme.css"), "utf8");
    expect(css).toMatch(/@custom-variant\s+dark\s*\(\s*&:is\(\.dark\s*,\s*\.dark \*\)\s*\)\s*;/);
  });
});
