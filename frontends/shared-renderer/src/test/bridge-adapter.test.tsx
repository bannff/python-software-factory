/**
 * BridgeAdapter context tests (Track 6, bd:python-factory-ons71).
 *
 * Pins the single data seam: useBridge() returns the host-supplied
 * adapter, and throws a loud error when no provider is mounted. A fake
 * adapter stands in for NextBridgeAdapter.
 */

import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import {
  BridgeAdapterProvider,
  useBridge,
  type BridgeAdapter,
} from "../index";

/** Minimal in-memory adapter — records calls, returns a canned envelope. */
class FakeAdapter implements BridgeAdapter {
  public calls: Array<{ name: string; args: Record<string, unknown> }> = [];
  async callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
    this.calls.push({ name, args });
    return { result: { ok: true, name } };
  }
}

describe("useBridge / BridgeAdapterProvider", () => {
  it("returns the host-supplied adapter inside a provider", () => {
    const adapter = new FakeAdapter();
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <BridgeAdapterProvider adapter={adapter}>{children}</BridgeAdapterProvider>
    );
    const { result } = renderHook(() => useBridge(), { wrapper });
    expect(result.current).toBe(adapter);
  });

  it("routes callTool through the supplied adapter", async () => {
    const adapter = new FakeAdapter();
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <BridgeAdapterProvider adapter={adapter}>{children}</BridgeAdapterProvider>
    );
    const { result } = renderHook(() => useBridge(), { wrapper });
    const res = await result.current.callTool("graph_get_stats", { limit: 5 });
    expect(adapter.calls).toEqual([{ name: "graph_get_stats", args: { limit: 5 } }]);
    expect(res).toEqual({ result: { ok: true, name: "graph_get_stats" } });
  });

  it("throws a clear error when no provider is mounted", () => {
    // Render a component that calls useBridge with no provider above it.
    function Bare() {
      useBridge();
      return null;
    }
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Bare />)).toThrow(/BridgeAdapterProvider/);
    spy.mockRestore();
  });

  it("provider renders its children", () => {
    const adapter = new FakeAdapter();
    render(
      <BridgeAdapterProvider adapter={adapter}>
        <span>seam-child</span>
      </BridgeAdapterProvider>,
    );
    expect(screen.queryByText("seam-child")).not.toBeNull();
  });
});
