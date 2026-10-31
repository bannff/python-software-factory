import { describe, expect, it } from "vitest";
import {
  initHistory, pushView, stepBack, stepForward, canBack, canForward, currentView,
} from "../view-history";

describe("view-history reducer (row 28, feature-map)", () => {
  it("starts with one entry and no back/forward", () => {
    const h = initHistory("welcome");
    expect(currentView(h)).toBe("welcome");
    expect(canBack(h)).toBe(false);
    expect(canForward(h)).toBe(false);
  });

  it("push records forward navigation and enables Back", () => {
    let h = initHistory("welcome");
    h = pushView(h, "sessions");
    h = pushView(h, "graph");
    expect(currentView(h)).toBe("graph");
    expect(canBack(h)).toBe(true);
    expect(canForward(h)).toBe(false);
  });

  it("push is a no-op when the view is already current", () => {
    const h = pushView(initHistory("welcome"), "welcome");
    expect(h).toEqual(initHistory("welcome"));
    expect(h.stack).toHaveLength(1);
  });

  it("Back then Forward walk the cursor without losing entries", () => {
    let h = pushView(pushView(initHistory("welcome"), "sessions"), "graph");
    h = stepBack(h);
    expect(currentView(h)).toBe("sessions");
    expect(canForward(h)).toBe(true);
    h = stepForward(h);
    expect(currentView(h)).toBe("graph");
  });

  it("navigating forward after Back truncates the old forward branch", () => {
    let h = pushView(pushView(initHistory("welcome"), "sessions"), "graph");
    h = stepBack(h); // at "sessions", forward = ["graph"]
    h = pushView(h, "settings"); // replaces "graph"
    expect(h.stack).toEqual(["welcome", "sessions", "settings"]);
    expect(canForward(h)).toBe(false);
  });

  it("Back/Forward are no-ops at the ends", () => {
    const start = initHistory("welcome");
    expect(stepBack(start)).toBe(start);
    expect(stepForward(start)).toBe(start);
  });
});
