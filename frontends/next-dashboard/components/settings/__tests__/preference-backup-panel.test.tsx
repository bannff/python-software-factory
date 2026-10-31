import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ exportPrefs: vi.fn(), importPrefs: vi.fn() }));
vi.mock("../preference-backup-api", () => ({
  exportPreferences: (...args: unknown[]) => mocks.exportPrefs(...args),
  importPreferences: (...args: unknown[]) => mocks.importPrefs(...args),
}));

import PreferenceBackupPanel from "../preference-backup-panel";

const snapshot = { plain_diffs: true, hidden_models: ["m1"], theme: "dark", revision: 3 };

beforeEach(() => {
  mocks.exportPrefs.mockReset().mockResolvedValue(snapshot);
  mocks.importPrefs.mockReset().mockResolvedValue(snapshot);
  URL.createObjectURL = vi.fn(() => "blob:mock");
  URL.revokeObjectURL = vi.fn();
});

describe("PreferenceBackupPanel (row 102, feature-map)", () => {
  it("downloads the real exported snapshot as a file", async () => {
    render(<PreferenceBackupPanel />);
    fireEvent.click(screen.getByRole("button", { name: /Download preferences/ }));
    await waitFor(() => expect(screen.getByText("Preferences downloaded.")).toBeTruthy());
    expect(mocks.exportPrefs).toHaveBeenCalledTimes(1);
  });

  it("restores an uploaded snapshot verbatim through the real import tool", async () => {
    render(<PreferenceBackupPanel />);
    const file = new File([JSON.stringify(snapshot)], "prefs.json", { type: "application/json" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(mocks.importPrefs).toHaveBeenCalledWith(snapshot));
    expect(await screen.findByText(/Preferences restored/)).toBeTruthy();
  });

  it("shows a truthful error instead of a silent failure on export", async () => {
    mocks.exportPrefs.mockRejectedValue(new Error("Preference backup is unavailable."));
    render(<PreferenceBackupPanel />);
    fireEvent.click(screen.getByRole("button", { name: /Download preferences/ }));
    expect((await screen.findByRole("alert")).textContent).toBe("Preference backup is unavailable.");
  });

  it("shows a truthful error instead of a silent failure on a malformed restore file", async () => {
    render(<PreferenceBackupPanel />);
    const file = new File(["not json"], "prefs.json", { type: "application/json" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(mocks.importPrefs).not.toHaveBeenCalled();
  });
});
