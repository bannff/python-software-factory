import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@copilotkit/react-core/v2", () => ({ useAgent: () => ({ agent: { threadId: "thread-1" } }) }));
vi.mock("@/lib/api", () => ({
  callTool: (...args: unknown[]) => mocks.callTool(...args),
  listPersonas: () => Promise.resolve({ count: 2, personas: [
    { id: "companion-x-default", name: "Companion X", description: "", model: null },
    { id: "reviewer", name: "Reviewer", description: "", model: null },
  ] }),
}));

import SchedulesView from "../schedules-view";

const listOk = (rows: unknown[]) => ({ ok: true, data: { schedules: rows } });
const SCHEDULE = {
  schedule_id: "sch_new", agent_id: "companion-x-default", task: "Do the thing",
  kind: "interval", interval_seconds: 3600, one_shot_at: null, cron_expression: null,
  timezone: "UTC", skip_dates: [], strict_schedule: false, state: "active",
  next_fire_at: null, last_fire_at: null, fire_sequence: 0, consecutive_failures: 0, revision: 1,
};

function defaultImpl(name: string) {
  if (name === "scheduler_list") return Promise.resolve(listOk([]));
  if (name === "scheduler_add") return Promise.resolve({ ok: true, data: { schedule: SCHEDULE } });
  return Promise.resolve({ ok: true, data: {} });
}

beforeEach(() => {
  mocks.callTool.mockReset().mockImplementation((name: string) => defaultImpl(name));
});

describe("Schedule creation", () => {
  it("opens the dialog from the header and the empty-state CTA", async () => {
    render(<SchedulesView />);
    expect(await screen.findByText(/No schedules yet/)).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "New schedule" })[0]);
    expect(await screen.findByRole("dialog")).toBeTruthy();
  });

  it("creates an interval schedule and closes the dialog", async () => {
    render(<SchedulesView />);
    fireEvent.click((await screen.findAllByRole("button", { name: "New schedule" }))[0]);
    fireEvent.change(await screen.findByLabelText("Task"), { target: { value: "Summarize activity" } });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("scheduler_add", {
      envelope: { thread_id: "thread-1" },
      agent_id: "companion-x-default", task: "Summarize activity", kind: "interval",
      interval_seconds: 3600, one_shot_at: null, cron_expression: null, timezone_name: "UTC",
    }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("switches timing kind and requires the matching field before allowing create", async () => {
    render(<SchedulesView />);
    fireEvent.click((await screen.findAllByRole("button", { name: "New schedule" }))[0]);
    fireEvent.change(await screen.findByLabelText("Task"), { target: { value: "Weekly report" } });
    fireEvent.click(screen.getByRole("radio", { name: "Cron expression" }));
    const create = screen.getByRole("button", { name: "Create schedule" });
    expect(create.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Cron expression"), { target: { value: "0 9 * * 1" } });
    expect(create.hasAttribute("disabled")).toBe(false);
    fireEvent.click(create);
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("scheduler_add", expect.objectContaining({
      kind: "cron", cron_expression: "0 9 * * 1",
    })));
  });

  it("keeps the dialog open and shows an error when creation fails", async () => {
    mocks.callTool.mockImplementation((name: string) =>
      name === "scheduler_add" ? Promise.resolve({ ok: false, error: { message: "boom" } }) : defaultImpl(name));
    render(<SchedulesView />);
    fireEvent.click((await screen.findAllByRole("button", { name: "New schedule" }))[0]);
    fireEvent.change(await screen.findByLabelText("Task"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("cancel closes without calling scheduler_add", async () => {
    render(<SchedulesView />);
    fireEvent.click((await screen.findAllByRole("button", { name: "New schedule" }))[0]);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mocks.callTool).not.toHaveBeenCalledWith("scheduler_add", expect.anything());
  });

  it("sends the agent picked from the registry", async () => {
    render(<SchedulesView />);
    fireEvent.click((await screen.findAllByRole("button", { name: "New schedule" }))[0]);
    await screen.findByRole("option", { name: "Reviewer" });
    fireEvent.change(screen.getByLabelText("Agent"), { target: { value: "reviewer" } });
    fireEvent.change(screen.getByLabelText("Task"), { target: { value: "Review" } });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("scheduler_add",
      expect.objectContaining({ agent_id: "reviewer" })));
  });

  it.each([
    ["scheduler_task_required", "Task", "Enter what this schedule should do."],
    ["scheduler_agent_not_found", "Agent", "That agent doesn't exist. Pick one from the list."],
    ["scheduler_interval_too_short", /^Interval/, "Use at least 60 seconds."],
    ["scheduler_one_shot_in_past", "Fire at", "Pick a time in the future."],
  ])("puts %s on its own field", async (code, label, message) => {
    mocks.callTool.mockImplementation((name: string) => name === "scheduler_add"
      ? Promise.resolve({ ok: false, error: { message: code } }) : defaultImpl(name));
    render(<SchedulesView />);
    fireEvent.click((await screen.findAllByRole("button", { name: "New schedule" }))[0]);
    fireEvent.change(await screen.findByLabelText("Task"), { target: { value: "Do it" } });
    if (code === "scheduler_one_shot_in_past") {
      fireEvent.click(screen.getByRole("radio", { name: "Once at a time" }));
      fireEvent.change(screen.getByLabelText("Fire at"), { target: { value: "2020-01-01T00:00" } });
    }
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));

    expect(await screen.findByText(message)).toBeTruthy();
    expect(screen.getByLabelText(label).getAttribute("aria-invalid")).toBe("true");
    expect(screen.queryByText(/Check the fields and try again/)).toBeNull();
  });

  it("keeps the generic text and the server's reason for an unmapped failure", async () => {
    mocks.callTool.mockImplementation((name: string) => name === "scheduler_add"
      ? Promise.resolve({ ok: false, error: { message: "scheduler_origin_not_found" } }) : defaultImpl(name));
    render(<SchedulesView />);
    fireEvent.click((await screen.findAllByRole("button", { name: "New schedule" }))[0]);
    fireEvent.change(await screen.findByLabelText("Task"), { target: { value: "Do it" } });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    expect(await screen.findByText(/didn't go through.*scheduler_origin_not_found/)).toBeTruthy();
  });
});
