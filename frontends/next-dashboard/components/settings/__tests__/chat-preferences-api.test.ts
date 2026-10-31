import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.call }));
import { getChatPreferences, updateChatPreferences } from "../chat-preferences-api";

const response = (data: unknown) => ({ tool: "ui", result: { ok: true, data } });

beforeEach(() => { mocks.call.mockReset(); });

describe("Chat preferences MCP API", () => {
  it("reads typed owner preferences", async () => {
    mocks.call.mockResolvedValue(response({ plain_diffs: false, hidden_models: ["model/a"], default_memory_mode: "persistent", collapse_message_input: true, pin_latest_prompt: true, revision: 2 }));
    await expect(getChatPreferences()).resolves.toEqual({ plainDiffs: false, hiddenModels: ["model/a"], defaultMemoryMode: "persistent", collapseMessageInput: true, pinLatestPrompt: true, revision: 2 });
    expect(mocks.call).toHaveBeenCalledWith("ui_get_chat_preferences");
  });

  it("updates the exact revision-fenced preference record", async () => {
    mocks.call.mockResolvedValue(response({ plain_diffs: true, hidden_models: [], default_memory_mode: "incognito", collapse_message_input: false, pin_latest_prompt: false, revision: 3 }));
    await expect(updateChatPreferences({ plainDiffs: true, hiddenModels: [], defaultMemoryMode: "incognito", collapseMessageInput: false, pinLatestPrompt: false, revision: 2 }))
      .resolves.toEqual({ plainDiffs: true, hiddenModels: [], defaultMemoryMode: "incognito", collapseMessageInput: false, pinLatestPrompt: false, revision: 3 });
    expect(mocks.call).toHaveBeenCalledWith("ui_update_chat_preferences", {
      plain_diffs: true, hidden_models: [], default_memory_mode: "incognito", collapse_message_input: false, pin_latest_prompt: false, expected_revision: 2,
    });
  });

  it("falls back to persistent/off when the backend omits or sends an unknown mode", async () => {
    mocks.call.mockResolvedValue(response({ plain_diffs: false, hidden_models: [], revision: 0 }));
    await expect(getChatPreferences()).resolves.toEqual({ plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent", collapseMessageInput: false, pinLatestPrompt: false, revision: 0 });
    mocks.call.mockResolvedValue(response({ plain_diffs: false, hidden_models: [], default_memory_mode: "bogus", revision: 0 }));
    await expect(getChatPreferences()).resolves.toEqual({ plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent", collapseMessageInput: false, pinLatestPrompt: false, revision: 0 });
  });

  it("row 12 (feature-map): sends collapse_message_input explicitly, never omitted", async () => {
    mocks.call.mockResolvedValue(response({ plain_diffs: false, hidden_models: [], default_memory_mode: "persistent", collapse_message_input: true, revision: 1 }));
    await updateChatPreferences({ plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent", collapseMessageInput: true, pinLatestPrompt: false, revision: 0 });
    expect(mocks.call).toHaveBeenCalledWith("ui_update_chat_preferences", expect.objectContaining({
      collapse_message_input: true,
    }));
  });

  it("row 10 (feature-map): sends pin_latest_prompt explicitly, never omitted", async () => {
    mocks.call.mockResolvedValue(response({ plain_diffs: false, hidden_models: [], default_memory_mode: "persistent", collapse_message_input: false, pin_latest_prompt: true, revision: 1 }));
    const result = await updateChatPreferences({ plainDiffs: false, hiddenModels: [], defaultMemoryMode: "persistent", collapseMessageInput: false, pinLatestPrompt: true, revision: 0 });
    expect(result.pinLatestPrompt).toBe(true);
    expect(mocks.call).toHaveBeenCalledWith("ui_update_chat_preferences", expect.objectContaining({
      pin_latest_prompt: true,
    }));
  });
});
