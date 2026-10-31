import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  toggleChat: vi.fn(), toggleTerminal: vi.fn(),
  shortcuts: {} as Record<string, string>,
}));
vi.mock("@/lib/workbench-context", () => ({
  useWorkbenchContext: () => ({ toggleChat: mocks.toggleChat, toggleTerminal: mocks.toggleTerminal }),
}));
vi.mock("@/components/settings/use-display-preferences", () => ({
  useDisplayPreferences: () => ({
    preferences: { theme: "system", terminalFontSize: 11, terminalShell: null, terminalCompletionEnabled: true,
      density: "comfortable", language: "en", shortcuts: mocks.shortcuts, revision: 1 },
    loading: false, error: null, refresh: vi.fn(),
  }),
}));

import { ShortcutListener } from "../shortcut-listener";

beforeEach(() => { mocks.toggleChat.mockReset(); mocks.toggleTerminal.mockReset(); mocks.shortcuts = {}; });

describe("ShortcutListener", () => {
  it("fires workbench toggles on default chords", () => {
    render(<ShortcutListener />);
    fireEvent.keyDown(window, { key: "j", metaKey: true });
    fireEvent.keyDown(window, { key: "`", ctrlKey: true });
    expect(mocks.toggleChat).toHaveBeenCalledTimes(1);
    expect(mocks.toggleTerminal).toHaveBeenCalledTimes(1);
  });

  it("honors an owner override and stops responding to the replaced default", () => {
    mocks.shortcuts = { toggle_chat: "alt+c" };
    render(<ShortcutListener />);
    fireEvent.keyDown(window, { key: "j", metaKey: true });
    expect(mocks.toggleChat).not.toHaveBeenCalled();
    fireEvent.keyDown(window, { key: "c", altKey: true });
    expect(mocks.toggleChat).toHaveBeenCalledTimes(1);
  });

  it("does not steal unmodified keys typed into inputs", () => {
    mocks.shortcuts = { toggle_terminal: "t" };
    const { container } = render(<><input aria-label="field" /><ShortcutListener /></>);
    const input = container.querySelector("input")!;
    fireEvent.keyDown(input, { key: "t" });
    expect(mocks.toggleTerminal).not.toHaveBeenCalled();
    fireEvent.keyDown(window, { key: "t" });
    expect(mocks.toggleTerminal).toHaveBeenCalledTimes(1);
  });
});
