import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  update: vi.fn(), announce: vi.fn(),
  prefs: { theme: "system", terminalFontSize: 11, terminalShell: null, terminalCompletionEnabled: true,
    density: "comfortable", language: "en", shortcuts: {} as Record<string, string>, revision: 2 },
}));
vi.mock("../use-display-preferences", () => ({
  useDisplayPreferences: () => ({ preferences: mocks.prefs, loading: false, error: null, refresh: vi.fn() }),
  announceDisplayPreferences: (...a: unknown[]) => mocks.announce(...a),
}));
vi.mock("../display-preferences-api", () => ({ updateDisplayPreferences: (...a: unknown[]) => mocks.update(...a) }));

import ShortcutsPanel from "../shortcuts-panel";

beforeEach(() => {
  mocks.prefs.shortcuts = {};
  mocks.update.mockReset().mockImplementation(async (value) => ({ ...value, revision: value.revision + 1 }));
  mocks.announce.mockReset();
});

describe("ShortcutsPanel overrides", () => {
  it("records a chord and persists it inside the full Display object", async () => {
    render(<ShortcutsPanel />);
    const button = screen.getByRole("button", { name: "Change shortcut for Open or close command palette" });
    fireEvent.click(button);
    expect(button.getAttribute("aria-pressed")).toBe("true");
    fireEvent.keyDown(button, { key: "P", metaKey: true, shiftKey: true });
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...mocks.prefs, shortcuts: { command_palette: "mod+shift+p" } }));
    expect(mocks.announce).toHaveBeenCalledWith(expect.objectContaining({ revision: 3 }));
  });

  it("refuses a chord already used by another action", async () => {
    render(<ShortcutsPanel />);
    const button = screen.getByRole("button", { name: "Change shortcut for Show or hide the chat sidebar" });
    fireEvent.click(button);
    fireEvent.keyDown(button, { key: "k", metaKey: true });
    expect((await screen.findByRole("alert")).textContent).toContain("Open or close command palette");
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("shows Reset only for overridden actions and clears the override", async () => {
    mocks.prefs.shortcuts = { toggle_terminal: "alt+t" };
    render(<ShortcutsPanel />);
    expect(screen.queryByRole("button", { name: "Reset shortcut for Open or close command palette" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reset shortcut for Show or hide the Terminal dock" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...mocks.prefs, shortcuts: {} }));
  });

  it("lists structural navigation keys without a change control", () => {
    render(<ShortcutsPanel />);
    expect(screen.getByText("Select first or last section")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Select first or last section/ })).toBeNull();
    expect(screen.getByText("Home")).toBeTruthy();
  });
});
