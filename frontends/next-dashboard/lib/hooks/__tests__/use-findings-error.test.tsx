import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { useFindings, useFindingsLoad } from "@/lib/hooks/use-findings";

beforeEach(() => { callTool.mockReset(); });

describe("useFindingsLoad", () => {
  it("reports no error and the rows when the read succeeds", async () => {
    callTool.mockResolvedValue({ result: { rows: [{ id: "g1", title: "A", severity: "low" }] } });
    const { result } = renderHook(() => useFindingsLoad([]));
    await waitFor(() => expect(result.current.findings).toHaveLength(1));
    expect(result.current.error).toBeNull();
  });

  it("reports an error when the tool call rejects", async () => {
    callTool.mockRejectedValue(new Error("network down"));
    const { result } = renderHook(() => useFindingsLoad([]));
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.findings).toEqual([]);
  });

  it("reports an error when the server answers with an ok:false envelope", async () => {
    callTool.mockResolvedValue({ tool: "graph_get_recent_findings", result: { schema_version: "v1", ok: false, data: null, error: "tool_execution_failed" } });
    const { result } = renderHook(() => useFindingsLoad([]));
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.findings).toEqual([]);
  });

  it("clears the error after a later successful read", async () => {
    callTool.mockRejectedValueOnce(new Error("boom")).mockResolvedValue({ result: { rows: [] } });
    const { result } = renderHook(() => useFindingsLoad([]));
    await waitFor(() => expect(result.current.error).not.toBeNull());
    window.dispatchEvent(new Event("companion-x:findings-changed"));
    await waitFor(() => expect(result.current.error).toBeNull());
  });

  it("keeps useFindings returning the plain list", async () => {
    callTool.mockResolvedValue({ result: { rows: [{ id: "g1", title: "A", severity: "low" }] } });
    const { result } = renderHook(() => useFindings([]));
    await waitFor(() => expect(result.current).toHaveLength(1));
  });
});
