import { describe, expect, it } from "vitest";
import { foldActivityByDay, type ActivityEvent } from "../activity-days";

// Local-noon-ish timestamps so day bucketing is stable regardless of TZ.
const NOW = new Date(2026, 8, 17, 12, 0, 0).getTime();       // Sep 17 2026
const at = (day: number, hour = 9) => new Date(2026, 8, day, hour, 0, 0).getTime();

describe("foldActivityByDay (row 30, feature-map)", () => {
  it("buckets by local day, newest first, with Today/Yesterday/date labels", () => {
    const events: ActivityEvent[] = [
      { at: at(17) }, { at: at(17, 10) }, { at: at(16) }, { at: at(15) },
    ];
    const days = foldActivityByDay(events, { now: NOW });
    expect(days.map((d) => d.label)).toEqual(["Today", "Yesterday", "Sep 15"]);
    expect(days.map((d) => d.count)).toEqual([2, 1, 1]);
  });

  it("aggregates per-project counts sorted desc", () => {
    const events: ActivityEvent[] = [
      { at: at(17), project: "alpha" },
      { at: at(17, 11), project: "beta" },
      { at: at(17, 13), project: "alpha" },
    ];
    const [today] = foldActivityByDay(events, { now: NOW });
    expect(today.byProject).toEqual([
      { project: "alpha", count: 2 }, { project: "beta", count: 1 },
    ]);
  });

  it("marks the oldest day as a floor when the log is capped", () => {
    const days = foldActivityByDay([{ at: at(17) }, { at: at(15) }], { now: NOW, capped: true });
    expect(days[0].floored).toBe(false);
    expect(days[days.length - 1].floored).toBe(true);
  });

  it("returns an empty list for no events", () => {
    expect(foldActivityByDay([], { now: NOW })).toEqual([]);
  });
});
