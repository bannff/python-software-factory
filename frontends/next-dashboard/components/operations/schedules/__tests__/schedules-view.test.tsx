import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import SchedulesView from "../schedules-view";

const future = new Date(Date.now() + 3_600_000).toISOString();

const intervalRow = {
  schedule_id: "sch_daily", agent_id: "companion-x-default",
  task: "Summarize overnight activity", kind: "interval", interval_seconds: 3_600,
  one_shot_at: null, cron_expression: null, timezone: "UTC", skip_dates: [],
  strict_schedule: false, state: "active", next_fire_at: future,
  last_fire_at: "2026-09-13T09:00:00Z", fire_sequence: 4, consecutive_failures: 0,
  revision: 2,
};
const cronRow = {
  schedule_id: "sch_report", agent_id: "reporter", task: "Weekly report",
  kind: "cron", interval_seconds: null, one_shot_at: null,
  cron_expression: "0 9 * * 1", timezone: "America/Chicago", skip_dates: [],
  strict_schedule: false, state: "auto_paused", next_fire_at: null,
  last_fire_at: "2026-09-07T14:00:00Z", fire_sequence: 2, consecutive_failures: 5,
  revision: 7,
};

const listOk = (rows: unknown[]) => ({ ok: true, data: { schedules: rows } });
const fireOk = { ok: true, data: { fire: { fire_sequence: 4, state: "succeeded" } } };

function defaultImpl(name: string) {
  if (name === "scheduler_list") return Promise.resolve(listOk([intervalRow, cronRow]));
  if (name === "scheduler_get_fire") return Promise.resolve(fireOk);
  return Promise.resolve({ ok: true, data: { schedule: intervalRow } });
}

beforeEach(() => {
  mocks.callTool.mockReset().mockImplementation((name: string) => defaultImpl(name));
});

describe("SchedulesView", () => {
  it("shows the loading state first, then the schedule cards", async () => {
    render(<SchedulesView />);
    expect(screen.getByText(/Loading schedules/)).toBeTruthy();
    expect(await screen.findByText("companion-x-default")).toBeTruthy();
    expect(screen.getByText("reporter")).toBeTruthy();
    expect(screen.getByText("Auto-paused")).toBeTruthy();
    expect(screen.getByText("Every hour")).toBeTruthy();
    expect(screen.getByText("Needs attention")).toBeTruthy();
  });

  it("renders the truthful empty state", async () => {
    mocks.callTool.mockImplementation(() => Promise.resolve(listOk([])));
    render(<SchedulesView />);
    expect(await screen.findByText(/No schedules yet/)).toBeTruthy();
  });

  it("renders error + retry and re-lists on retry", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "scheduler_list" ? Promise.reject(new Error("down")) : defaultImpl(name));
    render(<SchedulesView />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Schedules unavailable");
    mocks.callTool.mockImplementation((name: string) => defaultImpl(name));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("companion-x-default")).toBeTruthy();
  });

  it("pauses an active schedule with exact revision fencing and no identity args", async () => {
    render(<SchedulesView />);
    fireEvent.click(await screen.findByRole("button", { name: "Open schedule sch_daily" }));
    fireEvent.click(await screen.findByRole("button", { name: "Pause" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "scheduler_pause", { schedule_id: "sch_daily", expected_revision: 2 },
    ));
  });

  it("triggers a run-now with the record revision", async () => {
    render(<SchedulesView />);
    fireEvent.click(await screen.findByRole("button", { name: "Open schedule sch_daily" }));
    fireEvent.click(await screen.findByRole("button", { name: "Run now" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "scheduler_trigger", { schedule_id: "sch_daily", expected_revision: 2 },
    ));
  });

  it("resumes an auto-paused schedule", async () => {
    render(<SchedulesView />);
    fireEvent.click(await screen.findByRole("button", { name: "Open schedule sch_report" }));
    fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith(
      "scheduler_resume", { schedule_id: "sch_report", expected_revision: 7 },
    ));
  });

  it("refreshes the truth and warns on a revision conflict", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "scheduler_pause"
        ? Promise.resolve({ ok: false, error: { message: "schedule_revision_conflict" } })
        : defaultImpl(name));
    render(<SchedulesView />);
    fireEvent.click(await screen.findByRole("button", { name: "Open schedule sch_daily" }));
    const listCalls = () => mocks.callTool.mock.calls.filter((c) => c[0] === "scheduler_list").length;
    const before = listCalls();
    fireEvent.click(await screen.findByRole("button", { name: "Pause" }));
    expect(await screen.findByText(/changed elsewhere/)).toBeTruthy();
    expect(listCalls()).toBeGreaterThan(before); // refreshed rather than lied
  });

  it("focuses the detail heading for a deep-linked schedule and clears the intent", async () => {
    const onFocusHandled = vi.fn();
    render(<SchedulesView focusScheduleId="sch_report" onFocusHandled={onFocusHandled} />);
    const heading = await screen.findByRole("heading", { name: "reporter", level: 2 });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    expect(heading.getAttribute("tabindex")).toBe("-1");
    expect(onFocusHandled).toHaveBeenCalled();
  });

  it("marks the selected card with aria-current", async () => {
    render(<SchedulesView />);
    const card = await screen.findByRole("button", { name: "Open schedule sch_daily" });
    fireEvent.click(card);
    await waitFor(() => expect(
      screen.getByRole("button", { name: "Open schedule sch_daily" }).getAttribute("aria-current"),
    ).toBe("true"));
  });
});
