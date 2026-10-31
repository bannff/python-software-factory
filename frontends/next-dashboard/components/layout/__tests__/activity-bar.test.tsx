import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ActivityBar, NAV_GROUPS } from "@/components/layout/activity-bar";

const mocks = vi.hoisted(() => ({ count: vi.fn(() => 0) }));
vi.mock("@/lib/hooks/use-active-background-run-count", () => ({
  useActiveBackgroundRunCount: () => mocks.count(),
}));

describe("ActivityBar grouped navigation", () => {
  it("declares the exact group taxonomy, order, and membership", () => {
    expect(NAV_GROUPS.map((group) => group.caption)).toEqual([
      "Operations", "Analysis", "Intelligence", "System",
    ]);
    const membership = Object.fromEntries(
      NAV_GROUPS.map((group) => [group.caption, group.items.map((item) => item.id)]),
    );
    expect(membership).toEqual({
      Operations: ["welcome", "live", "sessions", "capabilities", "timeline-v2", "sandbox"],
      Analysis: ["graph", "findings", "evals", "metrics"],
      Intelligence: ["ml", "games", "blockchain"],
      System: ["settings"],
    });
  });

  it("keeps every destination reachable with an accessible label", () => {
    render(<ActivityBar activeView="welcome" onViewChange={vi.fn()} />);
    for (const group of NAV_GROUPS) {
      for (const item of group.items) {
        expect(screen.getByRole("button", { name: item.label })).toBeTruthy();
      }
    }
  });

  it("exposes each group as a labeled group with a caption in the tooltip", () => {
    render(<ActivityBar activeView="welcome" onViewChange={vi.fn()} />);
    const operations = screen.getByRole("group", { name: "Operations" });
    const capabilities = within(operations).getByRole("button", { name: "Agent Capabilities" });
    expect(within(capabilities).getByText("Operations")).toBeTruthy();
    expect(within(capabilities).getByRole("tooltip").textContent).toContain("Agent Capabilities");
  });

  it("bottom-pins the System (Settings) group", () => {
    render(<ActivityBar activeView="welcome" onViewChange={vi.fn()} />);
    const system = screen.getByRole("group", { name: "System" });
    expect(system.className).toContain("mt-auto");
    expect(within(system).getByRole("button", { name: "Settings" })).toBeTruthy();
  });

  it("marks the active destination with aria-current", () => {
    render(<ActivityBar activeView="settings" onViewChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Settings" }).getAttribute("aria-current"))
      .toBe("page");
    expect(screen.getByRole("button", { name: "Graph" }).getAttribute("aria-current"))
      .toBeNull();
  });

  it("marks Agent Capabilities active for a direct child route", () => {
    render(<ActivityBar activeView="artifacts" onViewChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Agent Capabilities" })
      .getAttribute("aria-current")).toBe("page");
    expect(screen.queryByRole("button", { name: "Artifacts" })).toBeNull();
  });

  it("shows no badge on Sessions when zero background runs are active", () => {
    render(<ActivityBar activeView="welcome" onViewChange={vi.fn()} />);
    const sessions = screen.getByRole("button", { name: "Sessions" });
    expect(within(sessions).queryByTestId("nav-badge")).toBeNull();
  });

  it("shows the real running-attempt count as a Sessions badge", () => {
    mocks.count.mockReturnValueOnce(3);
    render(<ActivityBar activeView="welcome" onViewChange={vi.fn()} />);
    const sessions = screen.getByRole("button", { name: "Sessions (3 running)" });
    expect(within(sessions).getByTestId("nav-badge").textContent).toBe("3");
    expect(screen.queryByTestId("nav-badge", { exact: false })).toBeTruthy();
    // Only Sessions carries a badge — every other destination stays plain.
    for (const group of NAV_GROUPS) {
      for (const item of group.items) {
        if (item.id === "sessions") continue;
        expect(within(screen.getByRole("button", { name: item.label }))
          .queryByTestId("nav-badge")).toBeNull();
      }
    }
  });
});
