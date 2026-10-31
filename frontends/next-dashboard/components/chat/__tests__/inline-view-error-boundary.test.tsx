/**
 * <InlineView> ErrorBoundary canary (bd:python-factory-lbvkh).
 *
 * Pre-fix repro: a child renderer that throws would bubble up through
 * React and surface as "Application error: client-side exception",
 * forcing the user to reload the entire chat panel.
 *
 * Post-fix contract:
 *   1. Throwing child does NOT crash the rendered tree — the parent
 *      mock surface still appears (we mount InlineView inside a
 *      sentinel wrapper to detect crash propagation).
 *   2. The fallback card renders with the error's message.
 *   3. When the surrounding `payload` reference changes, the boundary
 *      resets so a new (well-formed) message can paint normally.
 */

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { InlineView } from "../inline-view";

// Stub framer-motion to a passthrough so we don't pull animation timers
// into the test. The component only uses ``motion.div`` here.
vi.mock("framer-motion", () => ({
  motion: new Proxy(
    {},
    {
      get:
        () =>
          ({ children, ...rest }: React.PropsWithChildren<Record<string, unknown>>) =>
            React.createElement("div", rest, children),
    },
  ),
}));

// Mock the renderer's ComponentTree so we can plant a deliberate throw
// path. The real ComponentTree is exercised by the renderers-* tests.
vi.mock("@companion-x/shared-renderer", () => ({
  ComponentTree: ({ nodes }: { nodes: Array<{ component: string }> }) => {
    if (nodes.some((n) => n.component === "Boom")) {
      throw new Error("test-render-failure");
    }
    return <div data-testid="rendered-tree">{nodes.length} nodes</div>;
  },
}));

describe("InlineView — bd:lbvkh ErrorBoundary", () => {
  it("does not propagate errors to the outer parent when a child throws", () => {
    // Suppress React's expected error console output during the throw.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const Sentinel = () => <span data-testid="parent-still-alive">parent</span>;

    expect(() =>
      render(
        <div>
          <Sentinel />
          <InlineView
            payload={{
              name: "Diag",
              components: [
                {
                  id: "boom-1",
                  component: "Boom",
                  originalType: "Boom",
                  props: {},
                },
              ],
            }}
          />
        </div>,
      ),
    ).not.toThrow();

    expect(screen.queryByTestId("parent-still-alive")).not.toBeNull();
    errSpy.mockRestore();
  });

  it("renders the fallback card when a child renderer throws", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <InlineView
        payload={{
          components: [
            {
              id: "boom-1",
              component: "Boom",
              originalType: "Boom",
              props: {},
            },
          ],
        }}
      />,
    );

    expect(screen.queryByText("Inline view failed to render")).not.toBeNull();
    expect(screen.queryByText("test-render-failure")).not.toBeNull();
    errSpy.mockRestore();
  });

  it("recovers when the payload changes (resetKey behavior)", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const badPayload = {
      components: [
        {
          id: "boom-1",
          component: "Boom",
          originalType: "Boom",
          props: {},
        },
      ],
    };
    const goodPayload = {
      components: [
        {
          id: "ok-1",
          component: "Text",
          originalType: "Text",
          props: { text: "hi" },
        },
      ],
    };

    const { rerender } = render(<InlineView payload={badPayload} />);
    expect(screen.queryByText("Inline view failed to render")).not.toBeNull();

    act(() => {
      rerender(<InlineView payload={goodPayload} />);
    });

    expect(screen.queryByText("Inline view failed to render")).toBeNull();
    expect(screen.queryByTestId("rendered-tree")).not.toBeNull();
    errSpy.mockRestore();
  });

  it("renders normally for a well-formed payload (regression pin)", () => {
    render(
      <InlineView
        payload={{
          name: "Health",
          components: [
            {
              id: "t-1",
              component: "Text",
              originalType: "Text",
              props: { text: "all good" },
            },
          ],
        }}
      />,
    );
    expect(screen.queryByText("Health")).not.toBeNull();
    expect(screen.queryByTestId("rendered-tree")).not.toBeNull();
  });
});
