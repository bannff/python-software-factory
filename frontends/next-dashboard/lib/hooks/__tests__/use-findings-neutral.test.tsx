import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { FINDINGS_CHANGED, notifyFindingsChanged, useFindings } from "@/lib/hooks/use-findings";

const ok = (rows: unknown[]) => ({ result: { rows, count: rows.length } });
const neutral = {
  id: "f1", title: "Slow tool selection", severity: "high", run_id: "run-1",
  finding: { id: "f1", title: "Slow tool selection", severity: "high", state: "verified", kind: "eval", category: "latency",
    description: "p95 too high", evidence: "trace", remediation: "cache it",
    subject: { type: "tool", id: "search", location: "agent/search.py:10" },
    source: { brick: "evals", tool: "run", agent_id: "a1", run_id: "run-1", invocation_id: "", session_id: "" },
    taxonomy: [{ scheme: "owasp", id: "A01", label: "Broken access control" }], refs: [{ type: "graph_node", id: "f1" }, { type: "run", id: "run-1" }] },
};

beforeEach(() => { callTool.mockReset(); });

describe("useFindings with the neutral finding shape", () => {
  it("reads kind, state, subject and taxonomy from row.finding", async () => {
    callTool.mockResolvedValue(ok([neutral]));
    const { result } = renderHook(() => useFindings([]));
    await waitFor(() => expect(result.current).toHaveLength(1));
    const f = result.current[0];
    expect(f.type).toBe("eval");
    expect(f.kind).toBe("eval");
    expect(f.state).toBe("verified");
    expect(f.resource).toBe("search");
    expect(f.taxonomy).toEqual([{ scheme: "owasp", id: "A01", label: "Broken access control" }]);
    expect(f.run_id).toBe("run-1");
    expect(f.evidence).toBe("trace");
  });

  it("reads rows from the ToolResult envelope the app's callTool really returns", async () => {
    callTool.mockResolvedValue({ tool: "graph_get_recent_findings", result: { schema_version: "v1", ok: true, data: { rows: [neutral], count: 1 }, error: null } });
    const { result } = renderHook(() => useFindings([]));
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].kind).toBe("eval");
  });

  it("still maps a legacy row without row.finding", async () => {
    callTool.mockResolvedValue(ok([{ id: "g1", title: "Old", severity: "low", finding_type: "vulnerability", cwe: "CWE-79" }]));
    const { result } = renderHook(() => useFindings([]));
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0].type).toBe("vulnerability");
    expect(result.current[0].cwe).toBe("CWE-79");
  });

  it("refetches when a finding is recorded or its state changes", async () => {
    callTool.mockResolvedValue(ok([]));
    renderHook(() => useFindings([]));
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(1));
    act(() => notifyFindingsChanged());
    await waitFor(() => expect(callTool).toHaveBeenCalledTimes(2));
    expect(FINDINGS_CHANGED).toBeTruthy();
  });
});
