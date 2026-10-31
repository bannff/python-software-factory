import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MembersPage } from "../members-page";
import type { RosterMember } from "../roster-filter";
import type { ActivityEvent } from "../activity-days";

const M = (o: Partial<RosterMember>): RosterMember => ({
  id: o.name ?? "x", name: "x", starred: false, origin: "mine",
  state: "idle", lastActivityAt: null, ...o,
});
const MEMBERS: RosterMember[] = [M({ id: "ada", name: "Ada", lastActivityAt: 200 }), M({ id: "bos", name: "Bos" })];
const activityFor = (id: string): ActivityEvent[] => id === "ada" ? [{ at: Date.now(), project: "p" }] : [];

describe("MembersPage (row 30, feature-map)", () => {
  it("shows an honest empty state when no members are supplied", () => {
    render(<MembersPage members={[]} />);
    expect(screen.getByText(/members data source .* is not wired/i)).toBeTruthy();
  });

  it("selecting a member reveals their activity summary", () => {
    render(<MembersPage members={MEMBERS} activityFor={activityFor} />);
    expect(screen.getByText("Select a member to see their activity.")).toBeTruthy();
    const roster = within(screen.getByLabelText("Crew members roster"));
    fireEvent.click(roster.getByRole("button", { name: /Ada/ }));
    // heading + activity list now present
    expect(screen.getByRole("heading", { name: "Ada" })).toBeTruthy();
    expect(screen.getByLabelText("Activity by day")).toBeTruthy();
  });
});
