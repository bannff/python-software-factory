import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const focused = vi.hoisted(() => ({
  state: { entries: [], loading: false, error: null as string | null, available: true },
}));
vi.mock("@/lib/hooks/use-focused-run-entries", () => ({
  useFocusedRunEntries: () => focused.state,
}));
vi.mock("../timeline-run-trace", () => ({
  TimelineRunTrace: () => <div>exact trace</div>,
}));

import { TimelineFocusedRun } from "../timeline-focused-run";

beforeEach(() => {
  focused.state = { entries: [], loading: false, error: null, available: true };
});

describe("focused Timeline states", () => {
  it("distinguishes loading", () => {
    focused.state = { ...focused.state, loading: true };
    const { container } = render(<TimelineFocusedRun runId="run-a" onClear={vi.fn()} />);
    expect(container.querySelector(".animate-spin")).not.toBeNull();
    expect(screen.queryByText(/No attributed invocations/i)).toBeNull();
  });

  it("distinguishes unavailable without showing broad rows", () => {
    focused.state = { entries: [], loading: false, error: "exact API offline", available: false };
    render(<TimelineFocusedRun runId="run-a" onClear={vi.fn()} />);
    expect(screen.getByText(/Timeline unavailable for this run/i)).toBeTruthy();
    expect(screen.getByText("exact API offline")).toBeTruthy();
  });

  it("distinguishes authoritative empty", () => {
    render(<TimelineFocusedRun runId="run-a" onClear={vi.fn()} />);
    expect(screen.getByText(/No attributed invocations for this run/i)).toBeTruthy();
    expect(screen.queryByText("exact trace")).toBeNull();
  });
});
