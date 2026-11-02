import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import { ChatFilesTab } from "../chat-files-tab";

const listing = (entries: { path: string; kind: string }[]) =>
  ({ tool: "x", result: { result: { path: ".", entries } } });

beforeEach(() => mocks.callTool.mockReset());

describe("ChatFilesTab (row 24 — files in chat)", () => {
  it("lists directory entries and asks the agent about a file on click", async () => {
    mocks.callTool.mockResolvedValue(listing([
      { path: "src", kind: "dir" }, { path: "README.md", kind: "file" },
    ]));
    const sent = vi.fn();
    window.addEventListener("companion-x:send-prompt", (e) => sent((e as CustomEvent).detail), { once: true });
    render(<ChatFilesTab threadId="t1" />);
    await waitFor(() => expect(screen.getByText("README.md")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Ask about README.md" }));
    expect(sent).toHaveBeenCalledWith("Read @README.md and tell me what it is for.");
    expect(mocks.callTool).toHaveBeenCalledWith("devtools_list_dir", { path: ".", envelope: { thread_id: "t1" } });
  });

  it("navigates into a directory", async () => {
    mocks.callTool.mockResolvedValue(listing([{ path: "src", kind: "dir" }]));
    render(<ChatFilesTab threadId="t1" />);
    await waitFor(() => expect(screen.getByText("src")).toBeTruthy());
    fireEvent.click(screen.getByText("src"));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("devtools_list_dir", { path: "src", envelope: { thread_id: "t1" } }));
  });

  it("says why the directory could not be listed instead of a fixed sentence", async () => {
    mocks.callTool.mockResolvedValue({ tool: "x", result: { schema_version: "v1", ok: false, data: null, error: "tool_execution_failed" } });
    render(<ChatFilesTab threadId="t1" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("tool_execution_failed");
  });

  it.each([
    ["devtools_session_required", "Start a chat to browse files."],
    ["devtools_session_unavailable", "This chat’s session is gone."],
    ["devtools_project_unbound", "No project is bound to this chat."],
    ["devtools_binding_unavailable", "The project’s files can’t be reached."],
    ["devtools_path_refused", "That path is outside the workspace."],
  ])("shows a short state for %s", async (code, text) => {
    mocks.callTool.mockResolvedValue({ tool: "x", result: { schema_version: "v1", ok: false, data: null, error: code } });
    render(<ChatFilesTab threadId="t1" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(text);
  });
});
