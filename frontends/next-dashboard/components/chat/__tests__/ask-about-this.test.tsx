import { afterEach, describe, expect, it, vi } from "vitest";
import { createRef } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { AskAboutThisButton, AskAboutThisOverlay } from "../ask-about-this";

describe("AskAboutThisButton (row 19, feature-map)", () => {
  it("renders and fires onClick", () => {
    const onClick = vi.fn();
    render(<AskAboutThisButton top={10} left={20} onClick={onClick} />);
    const btn = screen.getByLabelText("Ask about this on the side");
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe("AskAboutThisOverlay (row 19, feature-map)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the button on a selection inside the container and calls onAsk with the text", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const textNode = document.createTextNode("selected span");
    container.appendChild(textNode);
    const ref = createRef<HTMLDivElement>();
    // Point the ref at our container.
    Object.defineProperty(ref, "current", { value: container, writable: true });

    vi.spyOn(window, "getSelection").mockReturnValue({
      isCollapsed: false,
      anchorNode: textNode,
      toString: () => "selected span",
      getRangeAt: () => ({ getBoundingClientRect: () => ({ bottom: 5, left: 5, top: 0, right: 0, width: 0, height: 0 }) }),
    } as unknown as Selection);

    const onAsk = vi.fn();
    render(<AskAboutThisOverlay containerRef={ref} onAsk={onAsk} />);
    fireEvent.mouseUp(document);
    const btn = screen.getByLabelText("Ask about this on the side");
    fireEvent.click(btn);
    expect(onAsk).toHaveBeenCalledWith("selected span");
  });

  it("renders nothing when the selection is collapsed", () => {
    const ref = createRef<HTMLDivElement>();
    Object.defineProperty(ref, "current", { value: document.createElement("div"), writable: true });
    vi.spyOn(window, "getSelection").mockReturnValue({ isCollapsed: true } as unknown as Selection);
    render(<AskAboutThisOverlay containerRef={ref} onAsk={vi.fn()} />);
    fireEvent.mouseUp(document);
    expect(screen.queryByLabelText("Ask about this on the side")).toBeNull();
  });
});
