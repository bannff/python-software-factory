import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MobileNav } from "@/components/layout/mobile-nav";
import { NAV_GROUPS } from "@/components/layout/activity-bar";

describe("MobileNav sheet", () => {
  it("exposes a >=44px named menu control", () => {
    render(<MobileNav activeView="welcome" onViewChange={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "Open navigation menu" });
    expect(trigger.className).toContain("h-11"); // 44px
    expect(trigger.className).toContain("w-11");
  });

  it("opens a labeled sheet grouping the exact NAV_GROUPS", () => {
    render(<MobileNav activeView="welcome" onViewChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation menu" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Navigate")).toBeTruthy();
    for (const group of NAV_GROUPS) {
      const region = within(dialog).getByRole("group", { name: group.caption });
      for (const item of group.items) {
        expect(within(region).getByRole("button", { name: item.label })).toBeTruthy();
      }
    }
  });

  it("navigates through sync + onViewChange and closes on selection", async () => {
    const onViewChange = vi.fn();
    window.history.pushState({}, "", "/");
    render(<MobileNav activeView="welcome" onViewChange={onViewChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Open navigation menu" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Agent Capabilities" }));
    expect(onViewChange).toHaveBeenCalledWith("capabilities");
    expect(window.location.pathname).toBe("/capabilities");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
