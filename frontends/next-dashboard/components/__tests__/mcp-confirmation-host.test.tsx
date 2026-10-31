import { afterEach, describe, expect, it } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { McpConfirmationHost } from "@/components/mcp-confirmation-host";
import {
  cancelAllConfirmations,
  requestConfirmation,
} from "@/lib/mcp-confirmation";

afterEach(() => cancelAllConfirmations());

describe("McpConfirmationHost", () => {
  it("resolves approval from the visible confirmation dialog", async () => {
    let decision!: Promise<"accept" | "decline" | "cancel">;
    act(() => { decision = requestConfirmation("Approve deployment?", "approved"); });
    render(<McpConfirmationHost />);

    expect(screen.getByText("Approve deployment?")).toBeTruthy();
    expect(screen.getByText("approved")).toBeTruthy();
    fireEvent.click(screen.getByTestId("mcp-confirmation-approve"));
    await expect(decision).resolves.toBe("accept");
  });

  it("distinguishes explicit denial from dismissal", async () => {
    let denied!: Promise<"accept" | "decline" | "cancel">;
    act(() => { denied = requestConfirmation("Approve deletion?", "approved"); });
    render(<McpConfirmationHost />);
    fireEvent.click(screen.getByTestId("mcp-confirmation-deny"));
    await expect(denied).resolves.toBe("decline");

    let cancelled!: Promise<"accept" | "decline" | "cancel">;
    act(() => { cancelled = requestConfirmation("Approve transfer?", "approved"); });
    const dialog = await screen.findByTestId("mcp-confirmation-dialog");
    fireEvent.keyDown(dialog, { key: "Escape" });
    await expect(cancelled).resolves.toBe("cancel");
  });

  it("cancels only the visible request when Escape dismisses a queue", async () => {
    let first!: Promise<"accept" | "decline" | "cancel">;
    let second!: Promise<"accept" | "decline" | "cancel">;
    let secondSettled = false;
    act(() => {
      first = requestConfirmation("Approve first operation?", "first");
      second = requestConfirmation("Approve second operation?", "second");
      void second.then(() => { secondSettled = true; });
    });
    render(<McpConfirmationHost />);

    fireEvent.keyDown(screen.getByTestId("mcp-confirmation-dialog"), {
      key: "Escape",
    });

    await expect(first).resolves.toBe("cancel");
    expect(await screen.findByText("Approve second operation?")).toBeTruthy();
    expect(secondSettled).toBe(false);

    fireEvent.click(screen.getByTestId("mcp-confirmation-approve"));
    await expect(second).resolves.toBe("accept");
  });
});
