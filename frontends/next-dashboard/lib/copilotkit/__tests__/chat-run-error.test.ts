import { beforeEach, describe, expect, it, vi } from "vitest";

const toast = vi.hoisted(() => ({ error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { chatRunErrorNotice, handleCopilotError } from "../chat-run-error";

const event = (message: string, context: Record<string, unknown> = {}) => ({
  error: new Error(message), code: "agent_run_error_event", context,
});

beforeEach(() => { toast.error.mockReset(); });

describe("chatRunErrorNotice", () => {
  it("recognises the typed code", () => {
    expect(chatRunErrorNotice(event("anything", { runtimeErrorCode: "model_not_configured" })))
      .toMatch(/no chat model is set up/i);
  });

  it("falls back to the message text when the stream carries no code", () => {
    const notice = chatRunErrorNotice(event("No chat model configured yet: set COMPANION_X_CHAT_MODEL (or an openai-compat profile)"));
    expect(notice).toMatch(/no chat model is set up/i);
  });

  it("never leaks the env var name into the notice", () => {
    const notice = chatRunErrorNotice(event("x", { runtimeErrorCode: "model_not_configured" })) ?? "";
    expect(notice).not.toContain("COMPANION_X_CHAT_MODEL");
  });

  it("leaves other errors to CopilotKit's default handling", () => {
    expect(chatRunErrorNotice(event("something else", { runtimeErrorCode: "other" }))).toBeNull();
  });
});

describe("handleCopilotError", () => {
  it("shows one notice for a known error", () => {
    handleCopilotError(event("x", { runtimeErrorCode: "model_not_configured" }));
    expect(toast.error).toHaveBeenCalledOnce();
  });

  it("stays quiet for unknown errors", () => {
    handleCopilotError(event("boom"));
    expect(toast.error).not.toHaveBeenCalled();
  });
});
