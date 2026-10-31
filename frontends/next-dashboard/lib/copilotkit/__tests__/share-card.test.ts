import { describe, expect, it } from "vitest";
import { buildShareCaption, messageText } from "../share-card";

describe("share-card helpers (row 13, feature-map)", () => {
  it("extracts plain text from string and parts-array content", () => {
    expect(messageText("hello")).toBe("hello");
    expect(messageText([{ type: "text", text: "a" }, { type: "text", text: "b" }])).toBe("a b");
    expect(messageText(undefined)).toBe("");
  });

  it("builds a caption from the first meaningful line, collapsing whitespace", () => {
    expect(buildShareCaption("  First line\n\nsecond")).toBe("First line");
    expect(buildShareCaption("multi   spaced   words")).toBe("multi spaced words");
  });

  it("caps a long caption and marks it with an ellipsis", () => {
    const long = "x".repeat(500);
    const caption = buildShareCaption(long);
    expect(caption.length).toBeLessThanOrEqual(261);
    expect(caption.endsWith("…")).toBe(true);
  });
});
