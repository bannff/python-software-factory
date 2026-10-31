import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { CrewActivitySummary } from "../crew-activity-summary";
import type { ActivityEvent } from "../activity-days";

const NOW = new Date(2026, 8, 17, 12, 0, 0).getTime();
const at = (day: number, hour = 9) => new Date(2026, 8, day, hour, 0, 0).getTime();

describe("CrewActivitySummary (row 30, feature-map)", () => {
  it("renders day rows with counts and per-project chips", () => {
    const events: ActivityEvent[] = [
      { at: at(17), project: "alpha" }, { at: at(17, 11), project: "alpha" }, { at: at(16) },
    ];
    render(<CrewActivitySummary events={events} now={NOW} />);
    const rows = within(screen.getByLabelText("Activity by day")).getAllByRole("listitem");
    expect(rows[0].textContent).toContain("Today");
    expect(rows[0].textContent).toContain("alpha · 2");
    expect(rows[1].textContent).toContain("Yesterday");
  });

  it("shows a floor marker on the oldest day when capped", () => {
    render(<CrewActivitySummary events={[{ at: at(17) }, { at: at(15) }]} capped now={NOW} />);
    const rows = within(screen.getByLabelText("Activity by day")).getAllByRole("listitem");
    expect(rows[rows.length - 1].textContent).toContain("≥ 1");
  });

  it("shows an empty state with no events", () => {
    render(<CrewActivitySummary events={[]} now={NOW} />);
    expect(screen.getByText("No recent activity.")).toBeTruthy();
  });
});
