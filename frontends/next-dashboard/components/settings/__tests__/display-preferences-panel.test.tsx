import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
const mocks = vi.hoisted(() => ({ update: vi.fn(), announce: vi.fn(), setTheme: vi.fn() }));
vi.mock("next-themes", () => ({ useTheme: () => ({ setTheme: mocks.setTheme }) }));
vi.mock("../use-display-preferences", () => ({
  useDisplayPreferences: () => ({
    preferences: {
      theme: "system", terminalFontSize: 11, terminalShell: null,
      terminalCompletionEnabled: true, density: "comfortable", language: "en", shortcuts: {}, revision: 2,
    },
    loading: false, error: null, refresh: vi.fn(),
  }),
  announceDisplayPreferences: (...args: unknown[]) => mocks.announce(...args),
}));
vi.mock("../display-preferences-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../display-preferences-api")>()),
  updateDisplayPreferences: (...args: unknown[]) => mocks.update(...args),
}));
vi.mock("@/lib/terminal-api", () => ({
  listTerminalShells: vi.fn(async () => ({ shells: ["/bin/zsh", "/bin/bash"] })),
}));
import DisplayPreferencesPanel from "../display-preferences-panel";
const BASE = {
  theme: "system", terminalFontSize: 11, terminalShell: null,
  terminalCompletionEnabled: true, density: "comfortable", language: "en", shortcuts: {}, revision: 2,
};
beforeEach(() => {
  mocks.update.mockReset().mockImplementation(async (value) => ({ ...value, revision: value.revision + 1 }));
  mocks.announce.mockReset(); mocks.setTheme.mockReset();
});
describe("DisplayPreferencesPanel", () => {
  it("persists and applies theme", async () => {
    render(<DisplayPreferencesPanel />);
    fireEvent.change(screen.getByRole("combobox", { name: "Theme" }), { target: { value: "dark" } });
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...BASE, theme: "dark" }));
    expect(mocks.setTheme).toHaveBeenCalledWith("dark");
  });
  it("persists bounded Terminal font size", async () => {
    render(<DisplayPreferencesPanel />);
    fireEvent.change(screen.getByRole("slider", { name: "Terminal font size" }), { target: { value: "16" } });
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...BASE, terminalFontSize: 16 }));
  });
  it("persists the selected default shell", async () => {
    render(<DisplayPreferencesPanel />);
    await screen.findByRole("option", { name: "/bin/zsh" });
    fireEvent.change(screen.getByRole("combobox", { name: "Default shell" }), { target: { value: "/bin/zsh" } });
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...BASE, terminalShell: "/bin/zsh" }));
  });
  it("toggles Terminal completion", async () => {
    render(<DisplayPreferencesPanel />);
    await screen.findByRole("option", { name: "/bin/zsh" });
    expect(screen.getByText(/command, option, and file-path suggestions/i)).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: "Enable Terminal completion" }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...BASE, terminalCompletionEnabled: false, density: "comfortable", language: "en" }));
  });
  it("persists density as part of the full Display object", async () => {
    render(<DisplayPreferencesPanel />);
    fireEvent.change(await screen.findByLabelText("Density"), { target: { value: "compact" } });
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...BASE, density: "compact" }));
    expect(mocks.announce).toHaveBeenCalledWith({ ...BASE, density: "compact", revision: 3 });
  });
  it("persists a BCP-47 language tag and offers the common set", async () => {
    render(<DisplayPreferencesPanel />);
    const select = await screen.findByLabelText("Language");
    expect(Array.from(select.querySelectorAll("option")).map((o) => o.getAttribute("value"))).toContain("pt-BR");
    fireEvent.change(select, { target: { value: "de" } });
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...BASE, language: "de" }));
  });
});
