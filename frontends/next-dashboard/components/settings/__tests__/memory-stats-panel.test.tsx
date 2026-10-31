import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import { MemoryStatsPanel } from "../memory-stats-panel";

beforeEach(() => mocks.callTool.mockReset());

describe("MemoryStatsPanel (row 109, feature-map)", () => {
  it("shows the total and by-type breakdown from memory_stats", async () => {
    mocks.callTool.mockResolvedValue({ tool: "memory_stats", result: {
      total_memories: 42, by_type: { preference: 30, project: 12 },
    } });
    render(<MemoryStatsPanel />);
    await waitFor(() => expect(screen.getByText("42")).toBeTruthy());
    expect(screen.getByText("preference")).toBeTruthy();
    expect(screen.getByText("30")).toBeTruthy();
    expect(mocks.callTool).toHaveBeenCalledWith("memory_stats", {});
  });

  it("shows an error when memory_stats is unavailable", async () => {
    mocks.callTool.mockRejectedValueOnce(new Error("unavailable"));
    render(<MemoryStatsPanel />);
    await waitFor(() => expect(screen.getByText(/Memory stats unavailable/i)).toBeTruthy());
  });
});
