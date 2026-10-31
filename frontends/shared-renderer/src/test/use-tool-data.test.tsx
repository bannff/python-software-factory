/**
 * useToolData tests (Track 6, bd:python-factory-ons71).
 *
 * Pins the loading → data / error transitions and the load-bearing
 * envelope unwrap (`res.result ?? res`) that survives the move onto
 * useBridge. The retry/timeout/abort machinery is preserved verbatim
 * from the in-tree hook; these tests exercise the happy path, the
 * envelope snapshot, and the post-retry error surface.
 */

import React from "react";
import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { BridgeAdapterProvider, useToolData, type BridgeAdapter } from "../index";

/** Adapter whose callTool resolves/rejects with a caller-chosen value. */
class ProgrammableAdapter implements BridgeAdapter {
  constructor(private readonly impl: (name: string, args: Record<string, unknown>) => Promise<unknown>) {}
  callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
    return this.impl(name, args);
  }
}

function wrapperFor(adapter: BridgeAdapter) {
  return ({ children }: { children: React.ReactNode }) => (
    <BridgeAdapterProvider adapter={adapter}>{children}</BridgeAdapterProvider>
  );
}

describe("useToolData", () => {
  it("starts loading then resolves data", async () => {
    const adapter = new ProgrammableAdapter(async () => ({ result: { value: 7 } }));
    const { result } = renderHook(() => useToolData("metrics_get", {}), {
      wrapper: wrapperFor(adapter),
    });
    // Loading kicks off synchronously on mount.
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeNull();
    expect(result.current.data).toEqual({ value: 7 });
  });

  it("unwraps the result envelope verbatim (res.result ?? res)", async () => {
    const enveloped = new ProgrammableAdapter(async () => ({
      result: { count: 42, items: [{ id: "a" }, { id: "b" }] },
      _meta: "ignored-by-unwrap",
    }));
    const { result } = renderHook(() => useToolData("kb_search", {}), {
      wrapper: wrapperFor(enveloped),
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // .result is peeled off; sibling envelope keys (_meta) are dropped.
    expect(result.current.data).toEqual({ count: 42, items: [{ id: "a" }, { id: "b" }] });
  });

  it("unwraps successful typed ToolResults after the gateway envelope", async () => {
    const typed = new ProgrammableAdapter(async () => ({
      tool: "workflow_get_dashboard_summary",
      result: { ok: true, data: { count: 42 }, error: null },
    }));
    const { result } = renderHook(() => useToolData("workflow_get_dashboard_summary", {}), {
      wrapper: wrapperFor(typed),
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ count: 42 });
  });

  it("falls back to the raw response when there is no result key", async () => {
    const bare = new ProgrammableAdapter(async () => ({ raw: true, n: 1 }));
    const { result } = renderHook(() => useToolData("plain_tool", {}), {
      wrapper: wrapperFor(bare),
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ raw: true, n: 1 });
  });

  it("surfaces an error after retries are exhausted", async () => {
    const failing = new ProgrammableAdapter(async () => {
      throw new Error("boom-tool-failure");
    });
    const { result } = renderHook(() => useToolData("breaks", {}), {
      wrapper: wrapperFor(failing),
    });
    // MAX_RETRIES=1 with a 2s backoff before the final failure.
    await waitFor(() => expect(result.current.error).not.toBeNull(), { timeout: 5000 });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toContain("boom-tool-failure");
    expect(result.current.data).toBeNull();
  });

  it("is inert when no toolName is supplied", async () => {
    const adapter = new ProgrammableAdapter(async () => ({ result: 1 }));
    const { result } = renderHook(() => useToolData(undefined, {}), {
      wrapper: wrapperFor(adapter),
    });
    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
