import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { Message } from "@ag-ui/core";
import { TurnMinimap, turnsFromMessages } from "../turn-minimap";

const user = (id: string, content: string): Message => ({ id, role: "user", content } as Message);
const assistant = (id: string, content: string): Message => ({ id, role: "assistant", content } as Message);

describe("turnsFromMessages (row 11, feature-map)", () => {
  it("returns one turn per non-empty user message, previews capped", () => {
    const turns = turnsFromMessages([
      user("1", "first ask"), assistant("2", "reply"), user("3", "  second   ask  "), user("4", "  "),
    ]);
    expect(turns).toEqual([{ id: "1", preview: "first ask" }, { id: "3", preview: "second ask" }]);
  });
});

describe("TurnMinimap (row 11, feature-map)", () => {
  it("renders nothing with fewer than two turns", () => {
    const { container } = render(<TurnMinimap turns={[{ id: "1", preview: "a" }]} onJump={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders one marker per turn and fires onJump with the index", () => {
    const onJump = vi.fn();
    render(<TurnMinimap turns={[{ id: "1", preview: "a" }, { id: "2", preview: "b" }]} onJump={onJump} />);
    const markers = screen.getAllByRole("button");
    expect(markers).toHaveLength(2);
    fireEvent.click(markers[1]);
    expect(onJump).toHaveBeenCalledWith(1);
  });
});
