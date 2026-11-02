import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Inbox, Play } from "lucide-react";
import { EmptyState } from "../empty-state";

describe("EmptyState", () => {
  it("offers an action that sends a prompt to the chat, and nothing without one", () => {
    const sent = vi.fn();
    window.addEventListener("companion-x:send-prompt", (e) => sent((e as CustomEvent).detail));
    const { rerender } = render(<EmptyState icon={Inbox} title="No findings" />);
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<EmptyState icon={Inbox} title="No findings"
      action={{ icon: Play, label: "Run a scan", prompt: "Run a security scan" }} />);
    fireEvent.click(screen.getByRole("button", { name: "Run a scan" }));
    expect(sent).toHaveBeenCalledWith("Run a security scan");
  });
});
