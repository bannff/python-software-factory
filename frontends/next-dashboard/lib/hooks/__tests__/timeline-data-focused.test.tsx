import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));
vi.mock("@/lib/hooks/use-health", () => ({
  useHealth: () => ({ timeline: { history: { available: true, reason: null } } }),
}));

import { callTool } from "@/lib/api";
import { useTimelineData } from "@/lib/hooks/use-timeline-data";

const tool = vi.mocked(callTool);
const response = (data: unknown) => ({
  tool: "graph_get_tool_invocations_for_run",
  result: { schema_version: "v1", ok: true, data },
});

beforeEach(() => tool.mockReset());

describe("focused Timeline history authority", () => {
  it("calls only the exact run tool with the full run ID", async () => {
    tool.mockResolvedValue(response({ rows: [{
      tool_name: "agent_reason", success: true, workflow_run_id: "run-full",
    }] }) as never);
    const { result } = renderHook(() => useTimelineData("run-full"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(tool).toHaveBeenCalledTimes(1);
    expect(tool).toHaveBeenCalledWith(
      "graph_get_tool_invocations_for_run", { run_id: "run-full", limit: 100 },
    );
    expect(result.current.entries[0]?.workflow_run_id).toBe("run-full");
  });

  it("reports exact API failure as unavailable with no fallback rows", async () => {
    tool.mockResolvedValue({
      tool: "graph_get_tool_invocations_for_run",
      result: { schema_version: "v1", ok: false, error: { message: "exact history offline" } },
    } as never);
    const { result } = renderHook(() => useTimelineData("run-full"));
    await waitFor(() => expect(result.current.error).toBe("exact history offline"));
    expect(result.current).toMatchObject({ entries: [], available: false });
    expect(tool).not.toHaveBeenCalledWith("graph_list_recent_tool_invocations", expect.anything());
  });
});
