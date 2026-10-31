import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ChatSidePanel, type ChatPanelTab } from "../chat-side-panel";

const tabs: ChatPanelTab[] = [
  { id: "summary", label: "Summary", render: () => <div>summary body</div> },
  { id: "pins", label: "Pins", render: () => <div>pins body</div> },
];

describe("ChatSidePanel (chat right-panel host)", () => {
  it("renders the active tab body and switches tabs on select", () => {
    const onSelect = vi.fn();
    render(<ChatSidePanel tabs={tabs} activeId="summary" onSelect={onSelect} onClose={vi.fn()} />);
    expect(screen.getByText("summary body")).toBeTruthy();
    expect(screen.queryByText("pins body")).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "Pins" }));
    expect(onSelect).toHaveBeenCalledWith("pins");
  });

  it("falls back to the first tab when activeId is unknown, and closes", () => {
    const onClose = vi.fn();
    render(<ChatSidePanel tabs={tabs} activeId="nope" onSelect={vi.fn()} onClose={onClose} />);
    expect(screen.getByText("summary body")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Close panel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders nothing with no tabs", () => {
    const { container } = render(<ChatSidePanel tabs={[]} activeId="x" onSelect={vi.fn()} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });
});
