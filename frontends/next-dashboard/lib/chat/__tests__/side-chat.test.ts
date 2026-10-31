import { describe, expect, it } from "vitest";
import { buildAskAboutPrompt, parseSideCommand, routeComposerSubmit } from "../side-chat";

describe("parseSideCommand (row 19, feature-map)", () => {
  it("detects /side and strips the prefix", () => {
    expect(parseSideCommand("/side what is this file")).toEqual({ isSide: true, query: "what is this file" });
  });
  it("detects /btw and strips the prefix", () => {
    expect(parseSideCommand("  /btw check the logs")).toEqual({ isSide: true, query: "check the logs" });
  });
  it("treats a bare /side as opening the panel with an empty query", () => {
    expect(parseSideCommand("/side")).toEqual({ isSide: true, query: "" });
  });
  it("leaves normal input untouched", () => {
    expect(parseSideCommand("deploy the service")).toEqual({ isSide: false, query: "deploy the service" });
  });
  it("does not treat /sidebar as a side command", () => {
    expect(parseSideCommand("/sidebar").isSide).toBe(false);
  });
});

describe("buildAskAboutPrompt (row 19, feature-map)", () => {
  it("wraps a selection and collapses whitespace", () => {
    expect(buildAskAboutPrompt("  the  quick\nbrown fox ")).toBe('About this: "the quick brown fox"');
  });
  it("returns empty for a blank selection", () => {
    expect(buildAskAboutPrompt("   \n ")).toBe("");
  });
  it("truncates a very long selection", () => {
    const prompt = buildAskAboutPrompt("x".repeat(600));
    expect(prompt.endsWith('…"')).toBe(true);
    expect(prompt.length).toBeLessThan(520);
  });
});

describe("routeComposerSubmit (row 19, feature-map)", () => {
  it("diverts a /side command to onSide (stripped) and does not send", () => {
    let sided = ""; let sent = "";
    const result = routeComposerSubmit("/side check logs", {
      onSide: (q) => { sided = q; }, onSend: (v) => { sent = v; },
    });
    expect(result).toBe("side");
    expect(sided).toBe("check logs");
    expect(sent).toBe("");
  });
  it("sends normal input to onSend and not onSide", () => {
    let sided = ""; let sent = "";
    const result = routeComposerSubmit("ship it", {
      onSide: (q) => { sided = q; }, onSend: (v) => { sent = v; },
    });
    expect(result).toBe("send");
    expect(sent).toBe("ship it");
    expect(sided).toBe("");
  });
});
