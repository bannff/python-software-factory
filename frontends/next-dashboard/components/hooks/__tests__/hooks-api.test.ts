import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ call: vi.fn(), tools: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.call, listTools: mocks.tools }));
import { deleteHook, hookAuthoringAvailable, listHooks, listInvocableTools,
  listRecentFirings, saveHook } from "../hooks-api";

beforeEach(() => { mocks.call.mockReset(); mocks.tools.mockReset(); });

describe("Hooks MCP API", () => {
  it("lists typed subscriptions with the tool name as `tool`", async () => {
    mocks.call.mockResolvedValue({ tool: "events_get_subscription_registry", result: { ok: true, data: {
      subscriptions: [{ id: "review", event_type: "workflow.failed", handler: "agent_read_skill", description: "Review", enabled: true, priority: 2 }],
    } } });
    await expect(listHooks()).resolves.toEqual([
      { id: "review", eventType: "workflow.failed", tool: "agent_read_skill", description: "Review", enabled: true },
    ]);
  });

  it("sends the exact upsert shape and detects authoring", async () => {
    mocks.tools.mockResolvedValue({ tools: ["events_authoring_upsert_subscription"], count: 1 });
    await expect(hookAuthoringAvailable()).resolves.toBe(true);
    mocks.call.mockResolvedValue({ tool: "events_authoring_upsert_subscription", result: { ok: true, data: { ok: true } } });
    const hook = { id: "review", eventType: "workflow.failed", tool: "agent_read_skill", description: "Review", enabled: false };
    await saveHook(hook);
    expect(mocks.call).toHaveBeenCalledWith("events_authoring_upsert_subscription", {
      subscription_id: "review",
      subscription_data: { id: "review", event_type: "workflow.failed", handler: "agent_read_skill", description: "Review", enabled: false, priority: 0, filters: {} },
      dry_run: false,
    });
  });

  it("deletes by subscription id and rejects a false server response", async () => {
    mocks.call.mockResolvedValueOnce({ tool: "events_authoring_delete_subscription", result: { ok: true, data: { ok: true } } });
    await expect(deleteHook("review")).resolves.toBeUndefined();
    expect(mocks.call).toHaveBeenCalledWith("events_authoring_delete_subscription", { subscription_id: "review" });
    mocks.call.mockResolvedValueOnce({ tool: "events_authoring_delete_subscription", result: { ok: true, data: { ok: false } } });
    await expect(deleteHook("review")).rejects.toThrow("Hook was not deleted.");
  });

  it("filters events_ tools out of the invocable-tool picker", async () => {
    mocks.tools.mockResolvedValue({ tools: ["agent_read_skill", "events_publish", "workflow_get_run"], count: 3 });
    await expect(listInvocableTools()).resolves.toEqual(["agent_read_skill", "workflow_get_run"]);
  });

  it("reads recent firings from history, skipping malformed rows", async () => {
    mocks.call.mockResolvedValueOnce({ tool: "events_list_history", result: { ok: true, data: {
      entries: [{ event_id: "e1", timestamp: "2026-09-15T00:00:00Z" }, { bad: "row" }],
    } } });
    await expect(listRecentFirings("workflow.failed")).resolves.toEqual([{ eventId: "e1", timestamp: "2026-09-15T00:00:00Z" }]);
    expect(mocks.call).toHaveBeenCalledWith("events_list_history", { event_type: "workflow.failed", limit: 10 });
  });
});
