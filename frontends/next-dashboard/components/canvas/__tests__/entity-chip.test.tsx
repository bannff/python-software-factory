import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EntityChip } from "../entity-chip";

describe("EntityChip", () => {
  it("renders the kind:value label as interactive button when onClick provided", () => {
    render(<EntityChip kind="run" value="chat-4fc" onClick={vi.fn()} />);
    expect(screen.getByRole("button").textContent).toBe("run:chat-4fc");
  });

  it("renders as non-interactive span when no onClick", () => {
    render(<EntityChip kind="brick" value="memory" />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("brick:memory")).toBeTruthy();
  });

  it("truncates long values to 12 chars", () => {
    render(<EntityChip kind="tx" value="abcdefghijklmnop" onClick={vi.fn()} />);
    expect(screen.getByRole("button").textContent).toBe("tx:abcdefghijkl");
  });

  it("fires onClick with mouse event on click", () => {
    const handler = vi.fn();
    render(<EntityChip kind="brick" value="memory" onClick={handler} />);
    fireEvent.click(screen.getByRole("button"));
    expect(handler).toHaveBeenCalledOnce();
    expect(handler.mock.calls[0][0]).toHaveProperty("stopPropagation");
  });

  it("has accessible aria-label for interactive chip", () => {
    render(<EntityChip kind="run" value="abc123" onClick={vi.fn()} />);
    expect(screen.getByRole("button").getAttribute("aria-label")).toBe(
      "Filter by run abc123",
    );
  });

  it("has accessible aria-label for non-interactive chip", () => {
    render(<EntityChip kind="session" value="s-123" />);
    expect(screen.getByText("session:s-123").getAttribute("aria-label")).toBe(
      "session s-123",
    );
  });
});

describe("EntityChip brick filter integration", () => {
  it("clicking a brick chip calls the filter handler with the brick value", () => {
    const filterBrick = vi.fn();
    // Simulate the pattern used in timeline-bubble-row: stopPropagation + call parent
    const handleClick = (e: React.MouseEvent) => {
      e.stopPropagation();
      filterBrick("graph");
    };
    render(<EntityChip kind="brick" value="graph" onClick={handleClick} />);
    fireEvent.click(screen.getByRole("button"));
    expect(filterBrick).toHaveBeenCalledWith("graph");
  });

  it("stopPropagation prevents parent row from expanding", () => {
    const parentClick = vi.fn();
    const chipClick = vi.fn((e: React.MouseEvent) => e.stopPropagation());
    render(
      <div onClick={parentClick}>
        <EntityChip kind="brick" value="memory" onClick={chipClick} />
      </div>,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(chipClick).toHaveBeenCalledOnce();
    expect(parentClick).not.toHaveBeenCalled();
  });
});
