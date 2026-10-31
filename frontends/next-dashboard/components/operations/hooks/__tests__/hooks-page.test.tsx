import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { HooksPage } from "../hooks-page";

describe("HooksPage (row 115, feature-map)", () => {
  it("documents the register_hook mechanism", () => {
    render(<HooksPage />);
    expect(screen.getByLabelText("Hooks manager")).toBeTruthy();
    expect(screen.getByText(/register_hook/)).toBeTruthy();
  });

  it("shows an honest empty-registry state (no persistent hook store)", () => {
    render(<HooksPage />);
    expect(screen.getByText(/No persistent hook registry/i)).toBeTruthy();
  });
});
