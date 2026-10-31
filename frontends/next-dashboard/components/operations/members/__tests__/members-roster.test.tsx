import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MembersRoster } from "../members-roster";
import type { RosterMember } from "../roster-filter";

const M = (o: Partial<RosterMember>): RosterMember => ({
  id: o.name ?? "x", name: "x", starred: false, origin: "mine",
  state: "idle", lastActivityAt: null, ...o,
});

const MEMBERS: RosterMember[] = [
  M({ name: "Ada", starred: true, state: "working", lastActivityAt: 300 }),
  M({ name: "Bos", starred: false, state: "idle", lastActivityAt: 100 }),
  M({ name: "Cyd", starred: true, state: "patrolling", lastActivityAt: 200 }),
];

const listNames = () =>
  within(screen.getByLabelText("Members")).getAllByRole("listitem")
    .map((li) => li.querySelector("span")?.textContent ?? "");

describe("MembersRoster (row 30, feature-map)", () => {
  it("renders the roster sorted by recent activity by default", () => {
    render(<MembersRoster members={MEMBERS} />);
    expect(listNames()).toEqual(["Ada", "Cyd", "Bos"]);
  });

  it("filters to starred with the toggle", () => {
    render(<MembersRoster members={MEMBERS} />);
    fireEvent.click(screen.getByLabelText("Starred only"));
    const names = listNames();
    expect(names).toContain("Ada");
    expect(names).toContain("Cyd");
    expect(names).not.toContain("Bos");
  });

  it("searches by name", () => {
    render(<MembersRoster members={MEMBERS} />);
    fireEvent.change(screen.getByLabelText("Search members"), { target: { value: "ad" } });
    expect(listNames()).toEqual(["Ada"]);
  });

  it("shows an empty state when nothing matches", () => {
    render(<MembersRoster members={MEMBERS} />);
    fireEvent.change(screen.getByLabelText("Search members"), { target: { value: "zzz" } });
    expect(screen.getByText("No members match.")).toBeTruthy();
  });
});
