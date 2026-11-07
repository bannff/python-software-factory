import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/hooks/use-copilot-state", () => ({ useCopilotCanvasState: () => ({ agentState: {} }) }));
vi.mock("@companion-x/shared-renderer", () => ({ ComponentTree: () => null }));
vi.mock("@/lib/chat/send-prompt", () => ({ sendPrompt: vi.fn() }));

import LiveView from "../live-view";
import { sendPrompt } from "@/lib/chat/send-prompt";

describe("Live view empty state", () => {
  it("hides tool and state-path names and offers a prompt action", () => {
    const { container } = render(<LiveView />);
    expect(container.textContent).not.toMatch(/ui_paint_canvas|state\.canvas/);
    fireEvent.click(screen.getByRole("button", { name: /paint something/i }));
    expect(sendPrompt).toHaveBeenCalledOnce();
  });
});
