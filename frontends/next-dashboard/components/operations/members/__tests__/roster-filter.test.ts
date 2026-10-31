import { describe, expect, it } from "vitest";
import { filterAndSortRoster, type RosterMember } from "../roster-filter";

const M = (over: Partial<RosterMember>): RosterMember => ({
  id: over.id ?? over.name ?? "x", name: "x", starred: false, origin: "mine",
  state: "idle", lastActivityAt: null, ...over,
});

const ROSTER: RosterMember[] = [
  M({ name: "Ada", starred: true, origin: "mine", state: "working", lastActivityAt: 300 }),
  M({ name: "Bos", starred: false, origin: "built-in", state: "idle", lastActivityAt: 100 }),
  M({ name: "Cyd", starred: true, origin: "from-packages", state: "patrolling", lastActivityAt: null }),
  M({ name: "Dot", starred: false, origin: "from-packages", state: "needs-you", lastActivityAt: 200 }),
];

const names = (r: RosterMember[]) => r.map((m) => m.name);

describe("filterAndSortRoster (row 30, feature-map)", () => {
  it("defaults to recent-activity sort, never-ran members last", () => {
    expect(names(filterAndSortRoster(ROSTER))).toEqual(["Ada", "Dot", "Bos", "Cyd"]);
  });

  it("sorts by name", () => {
    expect(names(filterAndSortRoster(ROSTER, { sort: "name" }))).toEqual(["Ada", "Bos", "Cyd", "Dot"]);
  });

  it("filters starred-only", () => {
    expect(names(filterAndSortRoster(ROSTER, { starredOnly: true, sort: "name" }))).toEqual(["Ada", "Cyd"]);
  });

  it("filters by live state and origin", () => {
    expect(names(filterAndSortRoster(ROSTER, { states: ["needs-you", "working"], sort: "name" })))
      .toEqual(["Ada", "Dot"]);
    expect(names(filterAndSortRoster(ROSTER, { origins: ["from-packages"], sort: "name" })))
      .toEqual(["Cyd", "Dot"]);
  });

  it("searches by name substring, case-insensitive", () => {
    expect(names(filterAndSortRoster(ROSTER, { search: "o" , sort: "name" }))).toEqual(["Bos", "Dot"]);
  });

  it("does not mutate the input array", () => {
    const before = names(ROSTER);
    filterAndSortRoster(ROSTER, { sort: "name" });
    expect(names(ROSTER)).toEqual(before);
  });
});
