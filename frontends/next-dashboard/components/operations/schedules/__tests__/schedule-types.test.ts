import { describe, expect, it } from "vitest";
import {
  classifyScheduleError, parseLastFire, parseScheduleList, parseScheduleOutput,
} from "../schedule-types";

const intervalRow = {
  schedule_id: "sch_daily",
  agent_id: "companion-x-default",
  task: "Summarize overnight activity",
  kind: "interval",
  interval_seconds: 86_400,
  one_shot_at: null,
  cron_expression: null,
  timezone: "UTC",
  skip_dates: ["2026-12-25"],
  strict_schedule: false,
  state: "active",
  next_fire_at: "2026-09-14T09:00:00Z",
  last_fire_at: "2026-09-13T09:00:00Z",
  fire_sequence: 4,
  consecutive_failures: 0,
  revision: 2,
};

// A ToolResult envelope as callTool hands it back (data on success).
const listEnvelope = (rows: unknown[]) => ({ ok: true, data: { schedules: rows } });

describe("parseScheduleList", () => {
  it("parses valid rows into camelCase schedules", () => {
    const [schedule] = parseScheduleList(listEnvelope([intervalRow]));
    expect(schedule.scheduleId).toBe("sch_daily");
    expect(schedule.kind).toBe("interval");
    expect(schedule.intervalSeconds).toBe(86_400);
    expect(schedule.skipDates).toEqual(["2026-12-25"]);
    expect(schedule.revision).toBe(2);
  });

  it("drops degraded rows without crashing (missing kind, bad revision, wrong enum)", () => {
    const rows = [
      intervalRow,
      { ...intervalRow, schedule_id: "no_kind", kind: undefined },
      { ...intervalRow, schedule_id: "bad_rev", revision: 0 },
      { ...intervalRow, schedule_id: "bad_state", state: "sleeping" },
      { schedule_id: "sparse" },
      "not-an-object",
    ];
    const parsed = parseScheduleList(listEnvelope(rows));
    expect(parsed.map((s) => s.scheduleId)).toEqual(["sch_daily"]);
  });

  it("returns [] when the envelope has no schedules array", () => {
    expect(parseScheduleList({ ok: true, data: {} })).toEqual([]);
    expect(parseScheduleList({ ok: true, data: { schedules: "nope" } })).toEqual([]);
  });
});

describe("parseScheduleOutput", () => {
  it("unwraps a single schedule", () => {
    expect(parseScheduleOutput({ ok: true, data: { schedule: intervalRow } }).scheduleId).toBe("sch_daily");
  });
  it("throws on an unparseable schedule", () => {
    expect(() => parseScheduleOutput({ ok: true, data: { schedule: { bad: 1 } } })).toThrow();
  });
});

describe("parseLastFire", () => {
  it("maps backend fire states to plain outcomes", () => {
    const mk = (state: string) => ({ ok: true, data: { fire: { fire_sequence: 4, state } } });
    expect(parseLastFire(mk("succeeded"))?.outcome).toBe("succeeded");
    expect(parseLastFire(mk("failed"))?.outcome).toBe("failed");
    expect(parseLastFire(mk("cancelled"))?.outcome).toBe("cancelled");
    expect(parseLastFire(mk("claimed"))?.outcome).toBe("running");
    expect(parseLastFire(mk("enrolled"))?.outcome).toBe("running");
  });
  it("returns null for an unknown or missing fire state", () => {
    expect(parseLastFire({ ok: true, data: { fire: { fire_sequence: 1, state: "weird" } } })).toBeNull();
    expect(parseLastFire({ ok: true, data: {} })).toBeNull();
  });
});

describe("classifyScheduleError", () => {
  it("classifies raw backend codes without surfacing them", () => {
    expect(classifyScheduleError(new Error("schedule_revision_conflict"))).toBe("conflict");
    expect(classifyScheduleError(new Error("schedule_not_found"))).toBe("deleted");
    expect(classifyScheduleError(new Error("schedule_invalid"))).toBe("error");
    expect(classifyScheduleError("boom")).toBe("error");
  });
});
