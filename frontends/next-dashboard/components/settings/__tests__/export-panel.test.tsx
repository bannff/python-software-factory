import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ preview: vi.fn(), run: vi.fn() }));
vi.mock("../export-api", async (original) => ({
  ...await original<typeof import("../export-api")>(),
  previewExport: (...args: unknown[]) => mocks.preview(...args),
  runExport: (...args: unknown[]) => mocks.run(...args),
}));

import ExportPanel from "../export-panel";

const preview = {
  bundleVersion: 1, adapter: "companion-x-v1", contentDigest: `sha256:${"a".repeat(64)}`,
  kinds: [
    { kind: "memory", count: 3, excluded: 0, digest: `sha256:${"b".repeat(64)}` },
    { kind: "lessons", count: 1, excluded: 1, digest: `sha256:${"c".repeat(64)}` },
  ],
};
const written = { ...preview, path: "/exports/backup.cxbundle.json", bytesWritten: 512 };

beforeEach(() => {
  mocks.preview.mockReset().mockResolvedValue(preview);
  mocks.run.mockReset().mockResolvedValue(written);
});

describe("ExportPanel (row 54 Portability, export half)", () => {
  it("previews only the selected kinds and shows per-kind counts", async () => {
    render(<ExportPanel />);
    fireEvent.click(screen.getByLabelText("Export knowledge base"));
    fireEvent.click(screen.getByLabelText("Export schedules"));
    fireEvent.click(screen.getByRole("button", { name: "Preview export" }));
    await waitFor(() => expect(screen.getAllByText("Export memory").length).toBeGreaterThan(1));
    expect(mocks.preview).toHaveBeenCalledWith(["memory", "lessons", "preferences"]);
    expect(screen.getAllByText("Export lessons").length).toBeGreaterThan(1);
  });

  it("writes the backup file and shows the real written path", async () => {
    render(<ExportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview export" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Write backup file/ })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Write backup file/ }));
    await waitFor(() => expect(screen.getByText(/Wrote 512 bytes to \/exports\/backup\.cxbundle\.json/)).toBeTruthy());
  });

  it("shows a truthful error instead of a silent failure", async () => {
    mocks.preview.mockRejectedValue(new Error("Export preview is unavailable."));
    render(<ExportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview export" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Export preview is unavailable.");
  });

  it("disables preview when every kind is deselected", () => {
    render(<ExportPanel />);
    for (const label of [
      "Export memory", "Export knowledge base", "Export lessons",
      "Export schedules", "Export display preferences",
    ]) fireEvent.click(screen.getByLabelText(label));
    expect((screen.getByRole("button", { name: "Preview export" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
