import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CapabilityTable, CAPABILITIES } from "../welcome-capabilities";

describe("CapabilityTable", () => {
  it("shows one row per capability and navigates on click", () => {
    const onNavigate = vi.fn();
    render(<CapabilityTable onNavigate={onNavigate} />);
    expect(screen.getAllByRole("button")).toHaveLength(CAPABILITIES.length);
    fireEvent.click(screen.getByRole("button", { name: /Findings/ }));
    expect(onNavigate).toHaveBeenCalledWith("findings");
  });

  it("shows each description as a visible row, not a tooltip", () => {
    render(<CapabilityTable onNavigate={vi.fn()} />);
    expect(screen.getByText(/knowledge graphs/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Graph/ }).getAttribute("title")).toBeNull();
  });
});
