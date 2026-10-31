import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, initial, animate, transition, ...props }: React.HTMLAttributes<HTMLDivElement> & Record<string, unknown>) => <div {...props}>{children}</div>,
    span: ({ children, initial, animate, transition, ...props }: React.HTMLAttributes<HTMLSpanElement> & Record<string, unknown>) => <span {...props}>{children}</span>,
  },
  useReducedMotion: () => true,
}));

import { SteerStatus } from "../steer-status";

describe("SteerStatus", () => {
  it.each([
    ["written", "Steering…"],
    ["consumed", "Steered into the running turn"],
    ["requeued", "Turn ended before this applied — runs as its own message"],
  ] as const)("renders truthful %s copy", (state, copy) => {
    render(<SteerStatus state={state} />);
    expect(screen.queryByText(copy)).not.toBeNull();
    expect(document.querySelector(`[data-steer-state="${state}"]`)).not.toBeNull();
  });

  it("never labels written or requeued as consumed", () => {
    const { rerender } = render(<SteerStatus state="written" />);
    expect(screen.queryByText("Steered into the running turn")).toBeNull();
    rerender(<SteerStatus state="requeued" />);
    expect(screen.queryByText("Steered into the running turn")).toBeNull();
  });
});
