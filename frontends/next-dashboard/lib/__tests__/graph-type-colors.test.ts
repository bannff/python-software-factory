import { describe, expect, it } from "vitest";
import { colorForType } from "@/lib/graph-data-utils";

describe("colorForType", () => {
  it("keeps the curated color for known types", () => {
    expect(colorForType("Agent")).toBe("#3b82f6");
  });

  it("gives an unmapped type a stable color of its own", () => {
    expect(colorForType("Transaction")).toBe(colorForType("Transaction"));
    expect(colorForType("Transaction")).not.toBe(colorForType("default"));
  });

  it("tells common unmapped types apart", () => {
    const colors = new Set(["Transaction", "CWECategory", "Node", "OCSFEventClass"].map(colorForType));
    expect(colors.size).toBeGreaterThan(2);
  });

  it("uses the neutral gray only for a missing type", () => {
    expect(colorForType("default")).toBe("#6b7280");
  });
});

describe("colorForType format", () => {
  it("stays a 6-digit hex so callers can append an alpha suffix", () => {
    expect(colorForType("Transaction")).toMatch(/^#[0-9a-f]{6}$/);
  });
});
