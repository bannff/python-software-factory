import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { NavHistoryArrows } from "../nav-history-arrows";

describe("NavHistoryArrows (row 28, feature-map)", () => {
  it("fires onBack/onForward and reflects enabled state", () => {
    const onBack = vi.fn();
    const onForward = vi.fn();
    render(<NavHistoryArrows canBack canForward onBack={onBack} onForward={onForward} />);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    fireEvent.click(screen.getByRole("button", { name: "Forward" }));
    expect(onBack).toHaveBeenCalledTimes(1);
    expect(onForward).toHaveBeenCalledTimes(1);
  });

  it("disables an arrow when there is nowhere to go", () => {
    render(<NavHistoryArrows canBack={false} canForward={false} onBack={vi.fn()} onForward={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Back" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Forward" })).toHaveProperty("disabled", true);
  });
});
