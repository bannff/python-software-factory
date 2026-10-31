import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  health: { connected: true, status: "healthy", totalTools: 42, brickCount: 20,
    healthyBricks: 19, bricks: {}, timeline: null, lastChecked: 123 },
}));
vi.mock("@/lib/hooks/use-health", () => ({ useHealth: () => mocks.health }));

import DiagnosticsBundlePanel from "../diagnostics-bundle-panel";

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:mock");
  URL.revokeObjectURL = vi.fn();
});

describe("DiagnosticsBundlePanel (row 101, feature-map)", () => {
  it("downloads a real bundle composed from already-fetched health data", () => {
    render(<DiagnosticsBundlePanel />);
    fireEvent.click(screen.getByRole("button", { name: /Download diagnostics bundle/ }));
    expect(screen.getByText("Diagnostics bundle downloaded.")).toBeTruthy();
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
  });

  it("discloses that no secrets or conversation content are included", () => {
    render(<DiagnosticsBundlePanel />);
    expect(screen.getByText(/never conversation content or credentials/i)).toBeTruthy();
  });
});
