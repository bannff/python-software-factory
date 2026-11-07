import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EmptyFindings } from "../findings-empty";

describe("EmptyFindings", () => {
  it("offers adding a finding in place, not a chat prompt", () => {
    const onAdd = vi.fn();
    render(<EmptyFindings onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: "Add a finding" }));
    expect(onAdd).toHaveBeenCalledOnce();
  });
});
