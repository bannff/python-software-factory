import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ActivityBar, CAPABILITY_VIEWS } from "@/components/layout/activity-bar";
import { ROUTED_VIEWS, syncCanvasRoute } from "@/lib/canvas-routes";

describe("Crews navigation", () => {
  beforeEach(() => { window.history.pushState({}, "", "/"); });
  afterEach(() => { window.history.pushState({}, "", "/"); });

  it("nests Crews under the single Agent Capabilities entry (M7.5 collapse)", () => {
    const onViewChange = vi.fn();
    render(<ActivityBar activeView="welcome" onViewChange={onViewChange} />);

    expect(screen.queryByTitle("Crews")).toBeNull();
    expect(CAPABILITY_VIEWS.has("crews")).toBe(true);

    fireEvent.click(screen.getByTitle("Agent Capabilities"));
    expect(onViewChange).toHaveBeenCalledWith("capabilities");
    expect(window.location.pathname).toBe("/capabilities");
  });

  it("highlights the Agent Capabilities entry while a Crews route is open", () => {
    render(<ActivityBar activeView="crews" onViewChange={vi.fn()} />);
    expect(screen.getByTitle("Agent Capabilities").getAttribute("aria-current"))
      .toBe("page");
  });

  it("registers /crews as a deep-linkable routed view", () => {
    expect(ROUTED_VIEWS.crews).toBe("/crews");
  });

  it("resets a routed path back to / for non-routed views", () => {
    window.history.pushState({}, "", "/crews");
    syncCanvasRoute("graph");
    expect(window.location.pathname).toBe("/");
  });

  it("pushes the routed path for a routed view", () => {
    syncCanvasRoute("crews");
    expect(window.location.pathname).toBe("/crews");
  });
});
