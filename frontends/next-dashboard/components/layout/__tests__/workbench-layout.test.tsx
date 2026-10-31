import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/canvas/canvas", () => ({ Canvas: () => <div data-testid="canvas" /> }));
vi.mock("@/components/chat/copilot-sidebar", () => ({
  CopilotChatSidebar: () => <div data-testid="chat" />,
}));
vi.mock("@/lib/hooks/use-chat-width", () => ({
  useChatWidth: () => ({ width: 440, setWidth: vi.fn() }),
}));

import { WorkbenchLayout } from "@/components/layout/workbench-layout";

const props = {
  activeView: "welcome" as const,
  chatOpen: true,
  tabs: [],
  activeTabId: "welcome",
  onViewChange: vi.fn(),
  onToggleChat: vi.fn(),
  onTabChange: vi.fn(),
  onTabClose: vi.fn(),
};

describe("WorkbenchLayout responsive shell", () => {
  it("keeps the desktop rail but hides it below md", () => {
    render(<WorkbenchLayout {...props} />);
    const wrapper = screen.getByRole("navigation", { name: "Primary" }).parentElement as HTMLElement;
    expect(wrapper.className).toContain("hidden");
    expect(wrapper.className).toContain("md:flex");
  });

  it("does not reserve chat-sidebar width below md", () => {
    render(<WorkbenchLayout {...props} />);
    const wrapper = screen.getByTestId("chat").parentElement as HTMLElement;
    expect(wrapper.className).toContain("hidden");
    expect(wrapper.className).toContain("md:flex");
  });

  it("renders the mobile menu control alongside a full-width canvas", () => {
    render(<WorkbenchLayout {...props} />);
    expect(screen.getByRole("button", { name: "Open navigation menu" })).toBeTruthy();
    expect(screen.getByTestId("canvas")).toBeTruthy();
  });
});
