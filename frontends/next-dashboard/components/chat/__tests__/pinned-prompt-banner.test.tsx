import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Message } from "@ag-ui/core";
import { PinnedPromptBanner, latestUserPrompt } from "../pinned-prompt-banner";

const user = (id: string, content: string): Message => ({ id, role: "user", content } as Message);
const assistant = (id: string, content: string): Message => ({ id, role: "assistant", content } as Message);

describe("latestUserPrompt (row 10)", () => {
  it("returns the most recent user message even while an assistant reply is last", () => {
    const messages = [user("1", "first"), assistant("2", "reply"), user("3", "latest ask"), assistant("4", "streaming…")];
    expect(latestUserPrompt(messages)).toBe("latest ask");
  });

  it("returns an empty string when there is no user message yet", () => {
    expect(latestUserPrompt([assistant("1", "hello")])).toBe("");
    expect(latestUserPrompt([])).toBe("");
  });
});

describe("PinnedPromptBanner (row 10)", () => {
  it("renders the pinned prompt text", () => {
    render(<PinnedPromptBanner prompt="Deploy the fix" />);
    expect(screen.getByLabelText("Pinned prompt")).toBeTruthy();
    expect(screen.getByText("Deploy the fix")).toBeTruthy();
  });

  it("renders nothing when the prompt is null or empty", () => {
    const { container, rerender } = render(<PinnedPromptBanner prompt={null} />);
    expect(container.firstChild).toBeNull();
    rerender(<PinnedPromptBanner prompt="" />);
    expect(container.firstChild).toBeNull();
  });
});
