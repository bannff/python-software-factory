import { describe, expect, it } from "vitest";
import { parseSessions } from "../use-session-list";

const session = {
  tenant_id: "tenant", owner_id: "owner", session_id: "s1", thread_id: "t1",
  title: "Provider migration", agent_id: "companion-x-default", model: "openrouter",
  mode: "", workspace: "", project: "", origin: "chat",
  crew_id: "", memory_scope: "",
  unread: false, tags: [], pinned_message_ids: [], summary: "", folder: "", pinned_rank: null,
  created_at: "2026-09-11T00:00:00Z", updated_at: "2026-09-11T00:01:00Z",
  archived_at: null, revision: 1,
};

describe("parseSessions", () => {
  it("unwraps the typed Session ToolResult", () => {
    const rows = parseSessions({
      tool: "session_list",
      result: { schema_version: "v1", ok: true, data: { sessions: [session] } },
    });
    expect(rows).toEqual([session]);
  });

  it("carries the crew/memory binding for SessionDeck restore", () => {
    const bound = { ...session, crew_id: "redteam-crew", memory_scope: "redteam" };
    const rows = parseSessions({
      tool: "session_list",
      result: { schema_version: "v1", ok: true, data: { sessions: [bound] } },
    });
    expect(rows[0].crew_id).toBe("redteam-crew");
    expect(rows[0].memory_scope).toBe("redteam");
  });

  it("defaults crew/memory to empty on older partial rows", () => {
    const { crew_id: _c, memory_scope: _m, ...legacy } = session;
    const rows = parseSessions({
      tool: "session_list",
      result: { schema_version: "v1", ok: true, data: { sessions: [legacy] } },
    });
    expect(rows[0].crew_id).toBe("");
    expect(rows[0].memory_scope).toBe("");
  });

  it("drops malformed rows", () => {
    expect(parseSessions({
      tool: "session_list",
      result: { schema_version: "v1", ok: true, data: {
        sessions: [{ session_id: "missing-fields" }, session],
      } },
    })).toEqual([session]);
  });
});
