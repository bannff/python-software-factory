/**
 * useAction dispatcher behaviour (bd:python-factory-3jcls.3 / bd:372an).
 *
 * Pins the four contracts the epic depends on:
 *   1. Everything routes through `BridgeAdapter` at the ONE dispatch tool.
 *   2. Errors are VISIBLE — never swallowed (the bd:372an defect).
 *   3. Refresh is an authoritative client re-fetch, not a view payload in
 *      the response.
 *   4. At-most-once-per-gesture: concurrent identical gestures collapse.
 *
 * The bridge is a fake here on purpose — this file tests the HOOK. The real
 * tool layer is exercised without mocks in
 * `components/ui/test/factory/ui/test_action_dispatch_real.py`.
 */
import React from "react";
import { describe, expect, it, vi } from "vitest";
import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import {
  BridgeAdapterProvider,
  ComponentTree,
  DISPATCH_TOOL,
  InvalidationProvider,
  TranscriptSinkProvider,
  resolveArgs,
  useAction,
  useRegisterRefetch,
  type ActionRef,
  type BridgeAdapter,
  type TranscriptEntry,
} from "../index";

class FakeBridge implements BridgeAdapter {
  public calls: Array<{ name: string; args: Record<string, unknown> }> = [];
  constructor(private readonly reply: (args: Record<string, unknown>) => unknown) {}
  callTool = async (name: string, args: Record<string, unknown>): Promise<unknown> => {
    this.calls.push({ name, args });
    return this.reply(args);
  };
}

const OK = (extra: Record<string, unknown> = {}) => () => ({
  result: { ok: true, tool: "cache_get", result: { found: true }, ...extra },
});

function wrap(bridge: BridgeAdapter, sink?: (e: TranscriptEntry) => void) {
  return ({ children }: { children: React.ReactNode }) => {
    const inner = <InvalidationProvider>{children}</InvalidationProvider>;
    return (
      <BridgeAdapterProvider adapter={bridge}>
        {sink ? <TranscriptSinkProvider sink={sink}>{inner}</TranscriptSinkProvider> : inner}
      </BridgeAdapterProvider>
    );
  };
}

const REF: ActionRef = { brick: "cache", tool: "cache_cache_get" };

describe("useAction", () => {
  it("dispatches through the bridge at the single dispatch tool", async () => {
    const bridge = new FakeBridge(OK());
    const { result } = renderHook(() => useAction("thread-7"), { wrapper: wrap(bridge) });
    await act(async () => { await result.current.dispatch(REF, { key: "k" }); });

    expect(bridge.calls).toHaveLength(1);
    expect(bridge.calls[0].name).toBe(DISPATCH_TOOL);
    expect(bridge.calls[0].args).toMatchObject({
      action: REF, args: { key: "k" }, thread_id: "thread-7",
    });
    expect(result.current.succeeded).toBe(true);
    expect(result.current.result).toEqual({ found: true });
    expect(result.current.error).toBeNull();
  });

  it("surfaces a server-side refusal as a visible error (bd:372an)", async () => {
    const bridge = new FakeBridge(() => ({ result: { ok: false, error: "nope" } }));
    const { result } = renderHook(() => useAction(), { wrapper: wrap(bridge) });
    await act(async () => { await result.current.dispatch(REF); });
    expect(result.current.error).toBe("nope");
    expect(result.current.succeeded).toBe(false);
  });

  it("surfaces a transport throw as a visible error", async () => {
    const bridge = new FakeBridge(() => { throw new Error("gateway down"); });
    const { result } = renderHook(() => useAction(), { wrapper: wrap(bridge) });
    await act(async () => { await result.current.dispatch(REF); });
    expect(result.current.error).toBe("gateway down");
  });

  it("collapses concurrent identical gestures to one call", async () => {
    const bridge = new FakeBridge(OK());
    const { result } = renderHook(() => useAction(), { wrapper: wrap(bridge) });
    await act(async () => {
      await Promise.all([
        result.current.dispatch(REF, { key: "k" }),
        result.current.dispatch(REF, { key: "k" }),
        result.current.dispatch(REF, { key: "k" }),
      ]);
    });
    expect(bridge.calls).toHaveLength(1);
  });

  it("does NOT collapse gestures with different args", async () => {
    const bridge = new FakeBridge(OK());
    const { result } = renderHook(() => useAction(), { wrapper: wrap(bridge) });
    await act(async () => {
      await Promise.all([
        result.current.dispatch(REF, { key: "a" }),
        result.current.dispatch(REF, { key: "b" }),
      ]);
    });
    expect(bridge.calls).toHaveLength(2);
  });

  it("passes a per-gesture UUID only when idempotency_arg is declared", async () => {
    const bridge = new FakeBridge(OK());
    const { result } = renderHook(() => useAction(), { wrapper: wrap(bridge) });
    const ref: ActionRef = { ...REF, idempotency_arg: "request_id" };
    await act(async () => { await result.current.dispatch(ref); });
    const sent = bridge.calls[0].args.args as Record<string, unknown>;
    expect(typeof sent.request_id).toBe("string");
    expect((sent.request_id as string).length).toBeGreaterThan(8);

    const plain = new FakeBridge(OK());
    const { result: r2 } = renderHook(() => useAction(), { wrapper: wrap(plain) });
    await act(async () => { await r2.current.dispatch(REF); });
    expect(plain.calls[0].args.args).toEqual({});
  });

  it("mirrors the call into the host transcript sink", async () => {
    const bridge = new FakeBridge(OK());
    const entries: TranscriptEntry[] = [];
    const { result } = renderHook(() => useAction(), {
      wrapper: wrap(bridge, (e) => entries.push(e)),
    });
    await act(async () => { await result.current.dispatch(REF, { key: "k" }); });
    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      toolName: "cache_get", args: { key: "k" }, ok: true,
    });
    expect(entries[0].toolCallId).toBeTruthy();
  });

  it("mirrors failures into the transcript too", async () => {
    const bridge = new FakeBridge(() => ({ result: { ok: false, error: "boom" } }));
    const entries: TranscriptEntry[] = [];
    const { result } = renderHook(() => useAction(), {
      wrapper: wrap(bridge, (e) => entries.push(e)),
    });
    await act(async () => { await result.current.dispatch(REF); });
    expect(entries[0]).toMatchObject({ ok: false, result: { error: "boom" } });
  });
});

describe("resolveArgs", () => {
  it("overlays literal args, $. bindings, then caller extras", () => {
    const action: ActionRef = {
      brick: "graph", tool: "graph_query",
      args: { limit: 10, key: "literal" },
      arg_bindings: { run_id: "$.run.id" },
    };
    const out = resolveArgs(action, { run: { id: "r-1" } }, { key: "override" });
    expect(out).toEqual({ limit: 10, key: "override", run_id: "r-1" });
  });

  it("drops bindings that do not resolve rather than sending undefined", () => {
    const action: ActionRef = {
      brick: "graph", tool: "graph_query", arg_bindings: { run_id: "$.missing.id" },
    };
    expect(resolveArgs(action, {})).toEqual({});
  });
});

describe("renderer integration", () => {
  const node = (type: string, props: Record<string, unknown>) => ({
    id: "n1", component: type, originalType: type, props,
  });

  it("Form dispatches its normalized ActionRef and shows the result", async () => {
    const bridge = new FakeBridge(OK());
    const Wrapper = wrap(bridge);
    render(
      <Wrapper>
        <ComponentTree
          nodes={[node("Form", {
            action: REF, submit_label: "Lookup",
            fields: [{ name: "key", type: "text", label: "Cache Key" }],
          })]}
        />
      </Wrapper>,
    );
    const button = screen.getByRole("button", { name: "Lookup" });
    await act(async () => { button.click(); });
    await waitFor(() => expect(bridge.calls).toHaveLength(1));
    expect(bridge.calls[0].name).toBe(DISPATCH_TOOL);
    expect(bridge.calls[0].args.action).toEqual(REF);
  });

  it("Form renders a server ingestion error instead of a dead control", () => {
    const bridge = new FakeBridge(OK());
    const Wrapper = wrap(bridge);
    render(
      <Wrapper>
        <ComponentTree
          nodes={[node("Form", {
            action: null, action_error: "action names unknown tool 'nope'",
            submit_label: "Go", fields: [],
          })]}
        />
      </Wrapper>,
    );
    expect(screen.getByRole("alert").textContent).toContain("unknown tool");
    expect(screen.getByRole("button", { name: "Go" })).toHaveProperty("disabled", true);
  });

  it("Button requires a second click when confirm is set", async () => {
    const bridge = new FakeBridge(OK());
    const Wrapper = wrap(bridge);
    render(
      <Wrapper>
        <ComponentTree
          nodes={[node("Button", { label: "Purge", action: { ...REF, confirm: true } })]}
        />
      </Wrapper>,
    );
    await act(async () => { screen.getByRole("button").click(); });
    expect(bridge.calls).toHaveLength(0);
    expect(screen.getByRole("button").textContent).toContain("Confirm: Purge");
    await act(async () => { screen.getByRole("button").click(); });
    await waitFor(() => expect(bridge.calls).toHaveLength(1));
  });

  it("Button surfaces a dispatch failure in the DOM", async () => {
    const bridge = new FakeBridge(() => ({ result: { ok: false, error: "refused" } }));
    const Wrapper = wrap(bridge);
    render(
      <Wrapper>
        <ComponentTree nodes={[node("Button", { label: "Run", action: REF })]} />
      </Wrapper>,
    );
    await act(async () => { screen.getByRole("button").click(); });
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("refused"));
  });
});

describe("invalidation", () => {
  it("re-fetches the tools named in invalidates, and carries no view payload", async () => {
    const bridge = new FakeBridge(OK({ invalidates: ["cache_cache_stats"] }));
    const refetch = vi.fn();

    function Registrar() {
      useRegisterRefetch("cache_cache_stats", refetch);
      return null;
    }
    const Wrapper = wrap(bridge);
    const { result } = renderHook(() => useAction(), {
      wrapper: ({ children }) => (
        <Wrapper><Registrar />{children}</Wrapper>
      ),
    });

    let outcome: { result?: unknown } = {};
    await act(async () => { outcome = await result.current.dispatch(REF); });
    expect(refetch).toHaveBeenCalledTimes(1);
    // Authoritative re-fetch, NOT a view payload smuggled in the response.
    expect(outcome).not.toHaveProperty("components");
  });
});
