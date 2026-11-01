import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import { ChatFilesTab } from "../chat-files-tab";

const listing = (entries: { path: string; kind: string }[]) =>
  ({ tool: "x", result: { result: { path: ".", entries } } });

beforeEach(() => mocks.callTool.mockReset());

describe("ChatFilesTab (row 24 — files in chat)", () => {
  it("lists directory entries and inserts a file reference on click", async () => {
    mocks.callTool.mockResolvedValue(listing([
      { path: "src", kind: "dir" }, { path: "README.md", kind: "file" },
    ]));
    const onInsert = vi.fn();
    render(<ChatFilesTab threadId="t1" onInsert={onInsert} />);
    await waitFor(() => expect(screen.getByText("README.md")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Reference README.md" }));
    expect(onInsert).toHaveBeenCalledWith("@README.md ");
    expect(mocks.callTool).toHaveBeenCalledWith("devtools_list_dir", { path: ".", envelope: { thread_id: "t1" } });
  });

  it("navigates into a directory", async () => {
    mocks.callTool.mockResolvedValue(listing([{ path: "src", kind: "dir" }]));
    render(<ChatFilesTab threadId="t1" onInsert={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("src")).toBeTruthy());
    fireEvent.click(screen.getByText("src"));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("devtools_list_dir", { path: "src", envelope: { thread_id: "t1" } }));
  });

  it("says why the directory could not be listed instead of a fixed sentence", async () => {
    mocks.callTool.mockResolvedValue({ tool: "x", result: { schema_version: "v1", ok: false, data: null, error: "tool_execution_failed" } });
    render(<ChatFilesTab threadId="t1" onInsert={vi.fn()} />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("tool_execution_failed");
  });
});
