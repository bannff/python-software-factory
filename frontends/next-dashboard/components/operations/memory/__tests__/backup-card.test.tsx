import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import BackupCard from "../backup-card";

const ok = (data: Record<string, unknown>) => ({ structuredContent: { ok: true, data } });

beforeEach(() => {
  mocks.callTool.mockReset();
  // jsdom does not implement object URLs; the export flow only needs the
  // calls to exist, not to produce a real blob URL.
  URL.createObjectURL = vi.fn(() => "blob:mock");
  URL.revokeObjectURL = vi.fn();
});

describe("BackupCard", () => {
  it("exports a single-page graph and reports success", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({
      backend: "persistent_networkx", supported: true,
      data_base64: btoa("{\"nodes\":[]}"), byte_size: 12, page: 0, page_count: 1, done: true,
    }));
    render(<BackupCard />);
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));
    await screen.findByText(/Graph exported \(1 page\)\./);
    expect(mocks.callTool).toHaveBeenCalledWith("graph_export", { page: 0 });
    expect(mocks.callTool).toHaveBeenCalledTimes(1);
  });

  it("pages through a multi-page export and reports the real page count", async () => {
    // Realistic paging: only the FINAL page carries base64 padding — these
    // two chunks concatenate into one valid base64 string, exactly as the
    // server's real byte-offset slicing produces.
    const fullBase64 = btoa("hello world, this is a two-page export");
    const mid = Math.floor(fullBase64.length / 2);
    mocks.callTool
      .mockResolvedValueOnce(ok({
        backend: "persistent_networkx", supported: true,
        data_base64: fullBase64.slice(0, mid), byte_size: 100, page: 0, page_count: 2, done: false,
      }))
      .mockResolvedValueOnce(ok({
        backend: "persistent_networkx", supported: true,
        data_base64: fullBase64.slice(mid), byte_size: 100, page: 1, page_count: 2, done: true,
      }));
    render(<BackupCard />);
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));
    await screen.findByText(/Graph exported \(2 pages\)\./);
    expect(mocks.callTool).toHaveBeenNthCalledWith(1, "graph_export", { page: 0 });
    expect(mocks.callTool).toHaveBeenNthCalledWith(2, "graph_export", { page: 1 });
  });

  it("reports an unsupported backend without claiming success", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({
      backend: "neo4j", supported: false, data_base64: "", byte_size: 0, page: 0, page_count: 1, done: true,
    }));
    render(<BackupCard />);
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));
    await screen.findByText(/nothing exportable/i);
  });

  it("arms then confirms a single-page import, and reports the real result", async () => {
    mocks.callTool
      .mockResolvedValueOnce(ok({ import_id: "imp_1" }))
      .mockResolvedValueOnce(ok({ import_id: "imp_1", received_pages: 1, total_pages: 1, imported: true }));
    render(<BackupCard />);

    const file = new File(["{\"nodes\":[]}"], "graph.json", { type: "application/json" });
    fireEvent.change(screen.getByLabelText(/Choose file/i, { selector: "input" }), { target: { files: [file] } });
    expect(await screen.findByText("graph.json")).toBeTruthy();

    const confirm = screen.getByRole("button", { name: /Replace whole graph with this file/ });
    fireEvent.click(confirm);
    await screen.findByText(/Graph imported\. The whole store was replaced\./);
    expect(mocks.callTool).toHaveBeenCalledWith("graph_import_begin", { total_pages: 1 });
    expect(mocks.callTool).toHaveBeenCalledWith("graph_import_page", expect.objectContaining({ import_id: "imp_1", page: 0 }));
  });

  it("shows a corrupt-file error without pretending the import worked", async () => {
    mocks.callTool
      .mockResolvedValueOnce(ok({ import_id: "imp_2" }))
      .mockResolvedValueOnce(ok({ import_id: "imp_2", received_pages: 1, total_pages: 1, imported: false, error: "snapshot checksum mismatch" }));
    render(<BackupCard />);

    const file = new File(["garbage"], "bad.json", { type: "application/json" });
    fireEvent.change(screen.getByLabelText(/Choose file/i, { selector: "input" }), { target: { files: [file] } });
    fireEvent.click(await screen.findByRole("button", { name: /Replace whole graph with this file/ }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/may be corrupt/i));
  });
});
