import { describe, expect, it } from "vitest";
import type { Schedule } from "../schedule-types";
import {
  describeShape, listOutcome, nextFireLabel, outcomeLabel, STATE_LABEL,
} from "../schedule-presenters";

const base: Schedule = {
  scheduleId: "s1", agentId: "a", task: "t", kind: "interval",
  intervalSeconds: 3_600, oneShotAt: null, cronExpression: null,
  timezone: "UTC", skipDates: [], strictSchedule: false, state: "active",
  nextFireAt: null, lastFireAt: null, fireSequence: 0, consecutiveFailures: 0,
  revision: 1,
};

describe("describeShape", () => {
  it("phrases intervals in plain units", () => {
    expect(describeShape({ ...base, intervalSeconds: 3_600 })).toBe("Every hour");
    expect(describeShape({ ...base, intervalSeconds: 1_800 })).toBe("Every 30 minutes");
    expect(describeShape({ ...base, intervalSeconds: 172_800 })).toBe("Every 2 days");
  });
  it("phrases one-shot and cron without exposing raw expressions", () => {
    const oneShot = describeShape({ ...base, kind: "one_shot", intervalSeconds: null, oneShotAt: "2026-09-14T09:00:00Z" });
    expect(oneShot.startsWith("Once, at")).toBe(true);
    const cron = describeShape({ ...base, kind: "cron", intervalSeconds: null, cronExpression: "0 9 * * 1", timezone: "America/Chicago" });
    expect(cron).toContain("repeating schedule");
    expect(cron).toContain("America/Chicago");
    expect(cron).not.toContain("*");
  });
});

describe("nextFireLabel", () => {
  it("does not schedule paused/auto-paused/completed states", () => {
    expect(nextFireLabel({ ...base, state: "paused" })).toContain("Paused");
    expect(nextFireLabel({ ...base, state: "auto_paused" })).toContain("Paused");
    expect(nextFireLabel({ ...base, state: "completed" })).toContain("Complete");
  });
  it("shows relative + absolute time when scheduled", () => {
    const future = new Date(Date.now() + 3_600_000).toISOString();
    const label = nextFireLabel({ ...base, nextFireAt: future });
    expect(label).toContain("in ");
    expect(label).toContain("·");
  });
});

describe("listOutcome", () => {
  it("flags failures, clean runs, and never-run without raw codes", () => {
    expect(listOutcome({ ...base, consecutiveFailures: 3 }).label).toBe("Needs attention");
    expect(listOutcome({ ...base, fireSequence: 5 }).label).toBe("Ran cleanly");
    expect(listOutcome(base).label).toBe("Not run yet");
  });
});

describe("labels", () => {
  it("maps states and outcomes to human copy", () => {
    expect(STATE_LABEL.auto_paused).toBe("Auto-paused");
    expect(outcomeLabel("failed")).toBe("Last run failed");
    expect(outcomeLabel("running")).toBe("Running now");
  });
});
