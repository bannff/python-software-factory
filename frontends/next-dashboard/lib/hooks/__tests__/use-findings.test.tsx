import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ActiveToolCall } from "@/lib/types";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => callTool(...args) }));

import { useFindings } from "@/lib/hooks/use-findings";

function call(name: string, result: unknown): ActiveToolCall {
  return { id: `${name}-1`, name, active: false, result: JSON.stringify(result) } as ActiveToolCall;
}

describe("useFindings", () => {
  it("collects findings from any tool, not only security-named ones", async () => {
    callTool.mockResolvedValue({ result: { rows: [] } });
    const { result } = renderHook(() => useFindings([
      call("evals_run_experiment", { findings: [{ title: "Regression in tool selection", severity: "high" }] }),
    ]));
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].title).toBe("Regression in tool selection");
  });

  it("does not invent a vulnerability label for an untyped finding", async () => {
    callTool.mockResolvedValue({ result: { rows: [{ id: "g1", title: "Slow query", severity: "low" }] } });
    const { result } = renderHook(() => useFindings([]));
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].type).toBe("other");
  });

  it("ignores a bare array from a tool that never claimed to return findings", async () => {
    callTool.mockResolvedValue({ result: { rows: [] } });
    const { result } = renderHook(() => useFindings([call("memory_list", [{ title: "not a finding" }])]));
    await waitFor(() => expect(callTool).toHaveBeenCalled());
    expect(result.current).toHaveLength(0);
  });
});
