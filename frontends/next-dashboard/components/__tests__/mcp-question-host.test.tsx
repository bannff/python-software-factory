import { afterEach, describe, expect, it } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { McpQuestionHost } from "@/components/mcp-question-host";
import {
  cancelAllQuestions,
  requestQuestion,
} from "@/lib/mcp-question";

afterEach(() => cancelAllQuestions());

describe("McpQuestionHost", () => {
  it("resolves the chosen option from the visible question dialog", async () => {
    let decision!: ReturnType<typeof requestQuestion>;
    act(() => {
      decision = requestQuestion("Which environment?", "answer", ["staging", "prod"]);
    });
    render(<McpQuestionHost />);

    expect(screen.getByText("Which environment?")).toBeTruthy();
    fireEvent.click(screen.getByTestId("mcp-question-option-prod"));
    await expect(decision).resolves.toEqual({ action: "answer", value: "prod" });
  });

  it("cancels on explicit Cancel and on dismissal", async () => {
    let cancelled!: ReturnType<typeof requestQuestion>;
    act(() => {
      cancelled = requestQuestion("Pick one", "answer", ["a", "b"]);
    });
    render(<McpQuestionHost />);
    fireEvent.click(screen.getByTestId("mcp-question-cancel"));
    await expect(cancelled).resolves.toEqual({ action: "cancel" });

    let dismissed!: ReturnType<typeof requestQuestion>;
    act(() => {
      dismissed = requestQuestion("Pick again", "answer", ["a", "b"]);
    });
    const dialog = await screen.findByTestId("mcp-question-dialog");
    fireEvent.keyDown(dialog, { key: "Escape" });
    await expect(dismissed).resolves.toEqual({ action: "cancel" });
  });

  it("advances the queue after the visible request settles", async () => {
    let first!: ReturnType<typeof requestQuestion>;
    let second!: ReturnType<typeof requestQuestion>;
    act(() => {
      first = requestQuestion("First question?", "answer", ["alpha", "beta"]);
      second = requestQuestion("Second question?", "answer", ["gamma", "delta"]);
    });
    render(<McpQuestionHost />);

    fireEvent.click(screen.getByTestId("mcp-question-option-alpha"));
    await expect(first).resolves.toEqual({ action: "answer", value: "alpha" });

    expect(await screen.findByText("Second question?")).toBeTruthy();
    fireEvent.click(screen.getByTestId("mcp-question-option-gamma"));
    await expect(second).resolves.toEqual({ action: "answer", value: "gamma" });
  });
});
