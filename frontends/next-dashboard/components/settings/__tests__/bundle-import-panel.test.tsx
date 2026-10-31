import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ preview: vi.fn(), start: vi.fn(), get: vi.fn() }));
vi.mock("../export-api", async (original) => ({
  ...await original<typeof import("../export-api")>(),
  previewBundleImport: (...args: unknown[]) => mocks.preview(...args),
}));
vi.mock("../import-api", async (original) => ({
  ...await original<typeof import("../import-api")>(),
  startMigration: (...args: unknown[]) => mocks.start(...args),
  getMigration: (...args: unknown[]) => mocks.get(...args),
}));

import BundleImportPanel from "../bundle-import-panel";

const preview = {
  planDigest: `sha256:${"a".repeat(64)}`, status: "committed",
  reports: [
    { kind: "memory", found: 2, eligible: 2, excluded: 0 },
    { kind: "kb", found: 5, eligible: 0, excluded: 5 },
  ],
  unsupportedKinds: ["kb"],
};
const started = { runId: "run-1", status: "running", progress: [], terminalReason: "" };
const completed = {
  runId: "run-1", status: "succeeded", terminalReason: "completed",
  progress: [{ kind: "memory", imported: 2, skipped: 0, failed: 0, cursor: 2 }],
};

beforeEach(() => {
  mocks.preview.mockReset().mockResolvedValue(preview);
  mocks.start.mockReset().mockResolvedValue(started);
  mocks.get.mockReset().mockResolvedValue(completed);
});

describe("BundleImportPanel (row 54 Portability, import half)", () => {
  it("previews a named bundle file and discloses unsupported kinds honestly", async () => {
    render(<BundleImportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview restore" }));
    await waitFor(() => expect(screen.getAllByText(/Knowledge base/).length).toBeGreaterThan(0));
    expect(mocks.preview).toHaveBeenCalledWith("backup.cxbundle.json");
    expect(screen.getByText(/cannot be restored yet/)).toBeTruthy();
  });

  it("requires confirmation before starting a restore, matching Export's merge-only posture", async () => {
    render(<BundleImportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview restore" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Start merge-only restore/ })).toBeTruthy());
    expect((screen.getByRole("button", { name: /Start merge-only restore/ }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox"));
    expect((screen.getByRole("button", { name: /Start merge-only restore/ }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("starts the restore with source=companion-x-v1 and shows progress", async () => {
    render(<BundleImportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview restore" }));
    await waitFor(() => screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Start merge-only restore/ }));
    await waitFor(() => expect(screen.getByText(/Restore succeeded/)).toBeTruthy());
    expect(mocks.start).toHaveBeenCalledWith(
      { planDigest: preview.planDigest }, ["memory", "kb"], "companion-x-v1",
    );
  });

  it("shows a truthful error instead of a silent failure", async () => {
    mocks.preview.mockRejectedValue(new Error("Bundle preview is unavailable."));
    render(<BundleImportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview restore" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Bundle preview is unavailable.");
  });
});
