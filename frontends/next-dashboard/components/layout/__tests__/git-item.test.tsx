import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
Element.prototype.hasPointerCapture = () => false;
Element.prototype.setPointerCapture = () => {};
Element.prototype.releasePointerCapture = () => {};
Element.prototype.scrollIntoView = () => {};

import { GitItem } from "@/components/layout/status-bar-items";

describe("repository popover", () => {
  it("shows a neutral remote label with no provider or region", () => {
    render(<GitItem />);
    fireEvent.click(screen.getByText("git"));
    expect(screen.getByText("Repository")).toBeTruthy();
    expect(screen.getByText("local workspace")).toBeTruthy();
    expect(screen.queryByText(/region/i)).toBeNull();
    expect(screen.queryByText(/repository provider/i)).toBeNull();
  });

  it("omits the branch row and the link when neither is configured", () => {
    render(<GitItem />);
    fireEvent.click(screen.getByText("git"));
    expect(screen.queryByText("Branch")).toBeNull();
    expect(screen.queryByText("Open repository")).toBeNull();
  });

  it("never renders an outbound link without a configured URL", () => {
    render(<GitItem />);
    fireEvent.click(screen.getByText("git"));
    expect(document.querySelector("a[target='_blank']")).toBeNull();
  });
});
