import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const agent = { addMessage: vi.fn() };
const copilotkit = { runAgent: vi.fn() };
vi.mock("@copilotkit/react-core/v2", () => ({
  useAgent: () => ({ agent }),
  useCopilotKit: () => ({ copilotkit }),
}));

import { sendPrompt, useSendPromptHandler } from "../send-prompt";

const assign = vi.fn();
beforeEach(() => {
  agent.addMessage.mockClear(); copilotkit.runAgent.mockClear(); assign.mockClear();
  sessionStorage.clear();
  Object.defineProperty(window, "location", { value: { ...window.location, assign }, writable: true, configurable: true });
});

describe("sendPrompt", () => {
  it("hands the prompt to a mounted chat and does not navigate", () => {
    renderHook(() => useSendPromptHandler("companion_x"));
    sendPrompt("Run an eval");
    expect(agent.addMessage).toHaveBeenCalledWith(expect.objectContaining({ role: "user", content: "Run an eval" }));
    expect(copilotkit.runAgent).toHaveBeenCalledTimes(1);
    expect(assign).not.toHaveBeenCalled();
  });

  it("queues the prompt and opens the chat when no chat is mounted", () => {
    sendPrompt("Run an eval");
    expect(assign).toHaveBeenCalledWith("/");
    expect(agent.addMessage).not.toHaveBeenCalled();
  });

  it("sends a queued prompt once when the chat appears", () => {
    sendPrompt("Run an eval");
    const first = renderHook(() => useSendPromptHandler("companion_x"));
    expect(agent.addMessage).toHaveBeenCalledWith(expect.objectContaining({ content: "Run an eval" }));
    expect(agent.addMessage).toHaveBeenCalledTimes(1);
    first.unmount();
    renderHook(() => useSendPromptHandler("companion_x"));
    expect(agent.addMessage).toHaveBeenCalledTimes(1);
  });
});
