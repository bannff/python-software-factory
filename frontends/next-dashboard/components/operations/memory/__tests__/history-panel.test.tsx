import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import MemoryHistoryPanel from "../history-panel";

const wrap = (data: unknown) => ({ tool: "t", result: { ok: true, data } });
const v1 = {
  id: "mem_1", user_id: "u", content: "v1 content", memory_type: "long_term",
  category: "preference", metadata: {}, relevance_score: 1,
  created_at: "2026-09-13T00:00:00Z", updated_at: null, expires_at: null,
};
const v2 = {
  id: "mem_2", user_id: "u", content: "v2 content", memory_type: "long_term",
  category: "preference", metadata: {}, relevance_score: 1,
  created_at: "2026-09-14T00:00:00Z", updated_at: null, expires_at: null,
};

beforeEach(() => mocks.callTool.mockReset());

describe("MemoryHistoryPanel", () => {
  it("shows an unsupported message when the active adapter has no history substrate", async () => {
    mocks.callTool.mockResolvedValue(wrap({ memory_id: "mem_1", supported: false, versions: [] }));
    render(<MemoryHistoryPanel memoryId="mem_1" onClose={() => {}} />);
    await screen.findByText(/no history to inspect/i);
  });

  it("shows a truthful 'never replaced' message for a single-version chain", async () => {
    mocks.callTool.mockResolvedValue(wrap({ memory_id: "mem_1", supported: true, versions: [v1] }));
    render(<MemoryHistoryPanel memoryId="mem_1" onClose={() => {}} />);
    await screen.findByText(/never been replaced/i);
  });

  it("lists every version newest first, with the newest marked Current", async () => {
    mocks.callTool.mockResolvedValue(wrap({ memory_id: "mem_1", supported: true, versions: [v2, v1] }));
    render(<MemoryHistoryPanel memoryId="mem_1" onClose={() => {}} />);
    await screen.findByText("v2 content");
    expect(screen.getByText("v1 content")).toBeTruthy();
    expect(screen.getByText("Current")).toBeTruthy();
    expect(screen.getByText("Replaced")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /restore/i })).toBeNull();
  });

  it("closes on request", async () => {
    mocks.callTool.mockResolvedValue(wrap({ memory_id: "mem_1", supported: true, versions: [v1] }));
    const onClose = vi.fn();
    render(<MemoryHistoryPanel memoryId="mem_1" onClose={onClose} />);
    await screen.findByText(/never been replaced/i);
    fireEvent.click(screen.getByLabelText("Close memory history"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows an unavailable message on a tool failure", async () => {
    mocks.callTool.mockRejectedValueOnce(new Error("boom"));
    render(<MemoryHistoryPanel memoryId="mem_1" onClose={() => {}} />);
    await screen.findByText(/history unavailable right now/i);
  });
});
