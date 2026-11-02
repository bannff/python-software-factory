import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { CapabilityGrid, CAPABILITIES } from "../welcome-capabilities";

describe("CapabilityGrid", () => {
  it("shows one icon card per capability and navigates on click", () => {
    const onNavigate = vi.fn();
    render(<CapabilityGrid onNavigate={onNavigate} />);
    expect(screen.getAllByRole("button")).toHaveLength(CAPABILITIES.length);
    fireEvent.click(screen.getByRole("button", { name: "Findings" }));
    expect(onNavigate).toHaveBeenCalledWith("findings");
  });

  it("keeps the description as a tooltip, not body text", () => {
    render(<CapabilityGrid onNavigate={vi.fn()} />);
    const card = screen.getByRole("button", { name: "Graph" });
    expect(card.getAttribute("title")).toMatch(/knowledge graphs/i);
    expect(screen.queryByText(/knowledge graphs/i)).toBeNull();
  });
});
