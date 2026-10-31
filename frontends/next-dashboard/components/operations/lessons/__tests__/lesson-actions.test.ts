import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import { acceptLesson, fetchLesson, rejectLesson, removeLesson } from "../lesson-actions";
import { parseLesson, parseLessons } from "../lesson-types";

const ID = "les_" + "a".repeat(32);
const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const lesson = {
  lesson_id: ID,
  rule: "Prefer dark mode",
  negative: "Avoid light backgrounds",
  category: "preference",
  scope: "global",
  scope_id: null,
  source: "feedback",
  evidence: ["Chat on 9/12"],
  status: "proposed",
  revision: 2,
  updated_at: "2026-09-13T00:00:00Z",
};

describe("lesson parsers", () => {
  it("drops rows that fail the strict typed contract", () => {
    const parsed = parseLessons(
      wrap({
        lessons: [
          lesson,
          { ...lesson, lesson_id: "not-a-lesson" },
          { ...lesson, status: "bogus" },
          { ...lesson, revision: "2" },
          { ...lesson, rule: "  " },
          "garbage",
        ],
      }),
    );
    expect(parsed).toHaveLength(1);
    expect(parsed[0]).toMatchObject({ lessonId: ID, status: "proposed", revision: 2 });
    expect(parsed[0].evidence).toEqual(["Chat on 9/12"]);
  });

  it("returns an empty list for a shapeless payload", () => {
    expect(parseLessons(wrap({}))).toEqual([]);
    expect(parseLessons(null)).toEqual([]);
  });

  it("unwraps a single lesson and throws when the record is missing", () => {
    expect(parseLesson(wrap({ lesson })).lessonId).toBe(ID);
    expect(() => parseLesson(wrap({}))).toThrow(/unavailable/i);
  });
});

describe("lesson curation actions send exact revision and session context", () => {
  const record = parseLesson(wrap({ lesson }));

  it("accepts with revision and active session context", async () => {
    mocks.callTool.mockReset().mockResolvedValue(wrap({ lesson: { ...lesson, status: "accepted", revision: 3 } }));
    const next = await acceptLesson(record, "thread");
    expect(mocks.callTool).toHaveBeenCalledWith("lessons_accept", { lesson_id: ID, expected_revision: 2, envelope: { session_id: "thread" } });
    expect(next.status).toBe("accepted");
  });

  it("rejects with revision and active session context", async () => {
    mocks.callTool.mockReset().mockResolvedValue(wrap({ lesson: { ...lesson, status: "rejected", revision: 3 } }));
    await rejectLesson(record, "thread");
    expect(mocks.callTool).toHaveBeenCalledWith("lessons_reject", { lesson_id: ID, expected_revision: 2, envelope: { session_id: "thread" } });
  });

  it("removes with revision and active session context", async () => {
    mocks.callTool.mockReset().mockResolvedValue(wrap({ lesson_id: ID, removed: true }));
    await removeLesson(record, "thread");
    expect(mocks.callTool).toHaveBeenCalledWith("lessons_remove", { lesson_id: ID, expected_revision: 2, envelope: { session_id: "thread" } });
  });

  it("fetches a single lesson by id with no identity args", async () => {
    mocks.callTool.mockReset().mockResolvedValue(wrap({ lesson }));
    await fetchLesson(ID);
    expect(mocks.callTool).toHaveBeenCalledWith("lessons_get", { lesson_id: ID });
  });
});
