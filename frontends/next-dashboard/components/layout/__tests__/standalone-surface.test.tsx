import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StandaloneSurface } from "../standalone-surface";

describe("StandaloneSurface (rows 125-130 scaffold)", () => {
  it("renders its child wrapped in a full-viewport labelled overlay", () => {
    render(<StandaloneSurface label="Embedded settings"><p>surface body</p></StandaloneSurface>);
    const overlay = screen.getByLabelText("Embedded settings");
    expect(overlay.className).toContain("fixed");
    expect(overlay.className).toContain("inset-0");
    expect(screen.getByText("surface body")).toBeTruthy();
  });

  it("falls back to a default label", () => {
    render(<StandaloneSurface><span>x</span></StandaloneSurface>);
    expect(screen.getByLabelText("Standalone surface")).toBeTruthy();
  });
});
