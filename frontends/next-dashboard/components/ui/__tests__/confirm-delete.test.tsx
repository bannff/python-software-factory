import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ConfirmDelete } from "../confirm-delete";

const setup = (onConfirm = vi.fn()) => {
  render(<ConfirmDelete label="Delete hook h1" onConfirm={onConfirm}>Delete</ConfirmDelete>);
  return onConfirm;
};

describe("ConfirmDelete", () => {
  it("does not fire on the first click, only arms", () => {
    const onConfirm = setup();
    fireEvent.click(screen.getByRole("button", { name: "Delete hook h1" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirm delete hook h1" })).toBeTruthy();
  });

  it("fires once on confirm and disarms", () => {
    const onConfirm = setup();
    fireEvent.click(screen.getByRole("button", { name: "Delete hook h1" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete hook h1" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Confirm delete hook h1" })).toBeNull();
  });

  it("cancel disarms without firing", () => {
    const onConfirm = setup();
    fireEvent.click(screen.getByRole("button", { name: "Delete hook h1" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete hook h1" })).toBeTruthy();
  });

  it("stays inert while disabled", () => {
    render(<ConfirmDelete label="Delete x" onConfirm={vi.fn()} disabled>Delete</ConfirmDelete>);
    expect((screen.getByRole("button", { name: "Delete x" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
