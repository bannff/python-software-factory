import { describe, expect, it } from "vitest";
import {
  ARTIFACT_SELECTION_MESSAGE,
  parseSelectionMessage,
  selectionReporterScript,
} from "../iframe-selection";

describe("parseSelectionMessage (row 65, feature-map)", () => {
  it("accepts a well-formed selection message and normalises whitespace", () => {
    expect(parseSelectionMessage({ type: ARTIFACT_SELECTION_MESSAGE, text: "  hello   world \n" }))
      .toEqual({ text: "hello world" });
  });

  it("rejects a wrong message type", () => {
    expect(parseSelectionMessage({ type: "other", text: "x" })).toBeNull();
  });

  it("rejects non-object / non-string / empty payloads", () => {
    expect(parseSelectionMessage(null)).toBeNull();
    expect(parseSelectionMessage("nope")).toBeNull();
    expect(parseSelectionMessage({ type: ARTIFACT_SELECTION_MESSAGE, text: 42 })).toBeNull();
    expect(parseSelectionMessage({ type: ARTIFACT_SELECTION_MESSAGE, text: "   " })).toBeNull();
  });

  it("caps the anchor length at 1000 chars", () => {
    const out = parseSelectionMessage({ type: ARTIFACT_SELECTION_MESSAGE, text: "z".repeat(1500) });
    expect(out?.text.length).toBe(1000);
  });
});

describe("selectionReporterScript (row 65, feature-map)", () => {
  it("emits a self-invoking mouseup→postMessage reporter under the shared type", () => {
    const s = selectionReporterScript();
    expect(s).toContain("mouseup");
    expect(s).toContain("postMessage");
    expect(s).toContain(ARTIFACT_SELECTION_MESSAGE);
  });
});
