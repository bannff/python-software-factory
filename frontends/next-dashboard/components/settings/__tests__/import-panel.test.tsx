import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ preview: vi.fn(), start: vi.fn(), get: vi.fn() }));
vi.mock("@/lib/hooks/use-mcp-connection", () => ({
  useMcpConnection: () => ({ ready: true, status: "connected" }),
}));
vi.mock("../import-api", async (original) => ({
  ...await original<typeof import("../import-api")>(),
  previewMigration: (...args: unknown[]) => mocks.preview(...args),
  startMigration: (...args: unknown[]) => mocks.start(...args),
  getMigration: (...args: unknown[]) => mocks.get(...args),
}));

import ImportPanel from "../import-panel";

const preview = {
  planDigest: `sha256:${"a".repeat(64)}`, status: "planned",
  reports: [
    { kind: "memory" as const, found: 3, eligible: 2, excluded: 1 },
    { kind: "lessons" as const, found: 1, eligible: 1, excluded: 0 },
  ],
  samples: [{ kind: "lessons" as const, sample: "Keep evidence" }],
};
const started = { runId: "run-1", status: "running", progress: [], terminalReason: "" };
const completed = {
  runId: "run-1", status: "succeeded", terminalReason: "completed",
  progress: [{ kind: "memory" as const, imported: 2, skipped: 1, failed: 0, cursor: 3 }],
};

beforeEach(() => {
  mocks.preview.mockReset().mockResolvedValue(preview);
  mocks.start.mockReset().mockResolvedValue(started);
  mocks.get.mockReset().mockResolvedValue(completed);
});

describe("ImportPanel", () => {
  it("previews only selected kinds and shows redacted plan evidence", async () => {
    render(<ImportPanel />);
    fireEvent.click(screen.getByLabelText("Schedules"));
    fireEvent.click(screen.getByLabelText("Preferences, projects & history"));
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledWith(["memory", "lessons"]));
    expect(await screen.findByText("3 eligible items in this immutable plan")).toBeTruthy();
    expect(screen.getByText("Keep evidence")).toBeTruthy();
    expect(screen.getByText(/Schedules arrive paused/)).toBeTruthy();
  });

  it("requires explicit confirmation before starting and shows typed progress", async () => {
    render(<ImportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    const start = await screen.findByRole("button", { name: "Start merge-only import" });
    expect((start as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/I reviewed this preview/));
    expect((start as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(start);
    await waitFor(() => expect(mocks.start).toHaveBeenCalledWith(preview,
      ["memory", "lessons", "schedules", "markdown"]));
    expect(await screen.findByRole("heading", { name: "Import succeeded" })).toBeTruthy();
    expect(screen.getByText("2 imported · 1 skipped · 0 failed")).toBeTruthy();
    expect(screen.getByText("Finished: completed")).toBeTruthy();
  });

  it("keeps preview failures visible without showing invented counts", async () => {
    mocks.preview.mockRejectedValue(new Error("migration_preview_unavailable"));
    render(<ImportPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect((await screen.findByRole("alert")).textContent).toContain("migration_preview_unavailable");
    expect(screen.queryByText(/eligible items/)).toBeNull();
  });
});
