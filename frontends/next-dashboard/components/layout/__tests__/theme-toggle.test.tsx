/**
 * P1 (c) owner report 2026-09-15: header theme toggle flashed then reverted.
 * The toggle only changed next-themes; `DisplayPreferenceSync` re-applied the
 * saved durable theme. Now the toggle writes the durable preference (full
 * object, CAS revision) and the sync keys only on the durable theme.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  setTheme: vi.fn(),
  resolved: "dark" as "dark" | "light",
  get: vi.fn(),
  update: vi.fn(),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: mocks.resolved, setTheme: mocks.setTheme }),
}));
vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));
vi.mock("@/components/settings/display-preferences-api", () => ({
  getDisplayPreferences: (...a: unknown[]) => mocks.get(...a),
  updateDisplayPreferences: (...a: unknown[]) => mocks.update(...a),
}));

import { ThemeToggle } from "../theme-toggle";
import DisplayPreferenceSync from "@/components/settings/display-preference-sync";

const SAVED = {
  theme: "dark", terminalFontSize: 12, terminalShell: "/bin/zsh",
  terminalCompletionEnabled: false, density: "comfortable", language: "en", shortcuts: {}, revision: 4,
};

beforeEach(() => {
  mocks.setTheme.mockReset(); mocks.get.mockReset(); mocks.update.mockReset();
  mocks.resolved = "dark";
  mocks.get.mockResolvedValue(SAVED);
  mocks.update.mockImplementation(async (next) => ({ ...next, revision: next.revision + 1 }));
});

describe("header theme toggle persists the durable Display preference", () => {
  it("writes the full preference object with CAS revision and applies the saved theme", async () => {
    render(<><DisplayPreferenceSync /><ThemeToggle /></>);
    const button = screen.getByRole("button", { name: "Toggle theme" });
    await waitFor(() => expect(button).toHaveProperty("disabled", false));
    await waitFor(() => expect(mocks.setTheme).toHaveBeenCalledWith("dark"));
    mocks.setTheme.mockClear();

    await act(async () => { fireEvent.click(button); });

    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ ...SAVED, theme: "light" }));
    await waitFor(() => expect(mocks.setTheme).toHaveBeenCalledWith("light"));
    // The sync must converge on the announced saved value — never re-apply "dark".
    expect(mocks.setTheme).not.toHaveBeenCalledWith("dark");
  });

  it("does not re-apply the saved theme when only the setTheme identity changes", async () => {
    const { rerender } = render(<DisplayPreferenceSync />);
    await waitFor(() => expect(mocks.setTheme).toHaveBeenCalledTimes(1));
    mocks.setTheme = vi.fn();
    rerender(<DisplayPreferenceSync />);
    await act(async () => {});
    expect(mocks.setTheme).not.toHaveBeenCalled();
  });

  it("reloads current values instead of applying a theme the store rejected", async () => {
    mocks.update.mockRejectedValueOnce(new Error("revision conflict"));
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Toggle theme" });
    await waitFor(() => expect(button).toHaveProperty("disabled", false));
    await act(async () => { fireEvent.click(button); });
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2));
    expect(mocks.setTheme).not.toHaveBeenCalledWith("light");
  });

  it("applies density and language to the document root from the durable preference", async () => {
    mocks.get.mockResolvedValue({ ...SAVED, density: "compact", language: "fr" });
    render(<DisplayPreferenceSync />);
    await waitFor(() => expect(document.documentElement.dataset.density).toBe("compact"));
    expect(document.documentElement.lang).toBe("fr");
  });
});
