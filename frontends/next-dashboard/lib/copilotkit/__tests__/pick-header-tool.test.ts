import { describe, expect, it } from "vitest";
import { pickHeaderTool } from "../tool-friendly-names";

const call = (title: string, caller?: string) => ({ title, caller, type: "tool_call" as const });

describe("pickHeaderTool", () => {
  it("ignores dashboard-originated polling reads", () => {
    const polls = [call("ui_get_chat_preferences"), call("session_list", "system:warmup"), call("events_query_recent")];
    expect(pickHeaderTool(polls)).toBeNull();
  });

  it("shows tool calls made by the chat agent", () => {
    const picked = pickHeaderTool([call("ui_get_chat_preferences"), call("kb_search", "chat:abcd1234")]);
    expect(picked?.meta.label).toBe("Knowledge search");
  });

  it("still skips agent-run infrastructure tools", () => {
    expect(pickHeaderTool([call("ui_start_session", "chat:abcd1234")])).toBeNull();
  });

  it("ignores bridged activity events, which are not the chat agent's own work", () => {
    const events = [
      { title: "Graph.Projection.Requested", type: "swarm_event" as const },
      { title: "Lesson.Removed", type: "swarm_event" as const },
    ];
    expect(pickHeaderTool(events)).toBeNull();
  });

  it("looks past activity events to the chat agent's latest tool call", () => {
    const picked = pickHeaderTool([{ title: "Lesson.Removed", type: "swarm_event" as const }, call("kb_search", "chat:abcd1234")]);
    expect(picked?.meta.label).toBe("Knowledge search");
  });
});
