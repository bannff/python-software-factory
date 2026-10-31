import { describe, expect, it } from "vitest";
import { hasUnsafeSegment, isUnsafeSegment } from "@/lib/terminal-path-guard";

describe("terminal BFF traversal guard", () => {
  it("rejects dot, dot-dot, separators, and encoded traversal", () => {
    for (const bad of [".", "..", "a/b", "a\\b", "%2e%2e", "%2f", "..%2f", "%5c", "\0"]) {
      expect(isUnsafeSegment(bad)).toBe(true);
    }
  });

  it("rejects malformed percent-encoding outright", () => {
    expect(isUnsafeSegment("%")).toBe(true);
  });

  it("allows the exact terminal route segments", () => {
    const routes = [
      ["sessions"],
      ["shells"],
      ["sessions", `term_${"a".repeat(32)}`, "attach"],
      ["sessions", `term_${"b".repeat(32)}`, "complete"],
    ];
    for (const path of routes) {
      expect(hasUnsafeSegment(path)).toBe(false);
    }
  });
});
