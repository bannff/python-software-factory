import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { TimelineBubbleRow } from "../timeline-bubble-row";
import type { TimelineEntry } from "@/lib/types";

const ENTRY_WITH_CHIPS: TimelineEntry = {
  id: "test-1",
  type: "tool_call",
  title: "process_workflow_rl",
  status: "completed",
  timestamp: Date.now(),
  detail: "games",
  workflow_run_id: "run-abc12345",
  session_id: "sess-xyz98765",
  duration: 1234,
};

describe("TimelineBubbleRow - no nested buttons (hydration guard)", () => {
  it("does not nest button inside button when collapsed with filter handlers", () => {
    const { container } = render(
      <TimelineBubbleRow
        entry={ENTRY_WITH_CHIPS}
        onFilterBrick={vi.fn()}
        onFilterRun={vi.fn()}
        onFilterSession={vi.fn()}
      />,
    );
    const nestedButtons = container.querySelectorAll("button button");
    expect(nestedButtons.length).toBe(0);
  });

  it("does not nest button inside button when expanded", () => {
    const { container } = render(
      <TimelineBubbleRow
        entry={ENTRY_WITH_CHIPS}
        onFilterBrick={vi.fn()}
        onFilterRun={vi.fn()}
        onFilterSession={vi.fn()}
      />,
    );
    // Expand by clicking the trigger
    const trigger = container.querySelector("button");
    trigger?.click();
    const nestedButtons = container.querySelectorAll("button button");
    expect(nestedButtons.length).toBe(0);
  });

  it("renders multiple sibling buttons (trigger + chips) at same level", () => {
    const { container } = render(
      <TimelineBubbleRow
        entry={ENTRY_WITH_CHIPS}
        onFilterBrick={vi.fn()}
        onFilterRun={vi.fn()}
        onFilterSession={vi.fn()}
      />,
    );
    // 1 toggle + 3 chips (brick, run, session) = 4 buttons total
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(4);
  });
});
