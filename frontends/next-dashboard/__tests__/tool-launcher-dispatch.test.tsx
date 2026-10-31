/**
 * The palette's submit seam (bd:3jcls.4).
 *
 * `useAction` is the ONLY thing mocked. Everything below it is real — the
 * schema-derived form, the resolved-call preview, the required-field gate — so
 * this pins the boundary the palette owns (does it build the right `ActionRef`
 * and hand it to the one dispatcher?) without re-testing the dispatcher, which
 * has its own suite in `shared-renderer`.
 *
 * There is deliberately no `fetch` assertion here: a second dispatch path is
 * prevented structurally by the grep canary over `shared-renderer/src`, not by
 * a unit test.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "./fixtures/real-tool-schemas.json";
import type { CatalogTool } from "@/lib/tool-catalog";

const dispatch = vi.fn(() => Promise.resolve({ ok: true, result: "OK" }));
let actionState = { pending: false, error: null as string | null, result: null as unknown, succeeded: false };

vi.mock("@companion-x/shared-renderer", () => ({
  useAction: () => ({ dispatch, reset: vi.fn(), ...actionState }),
}));

// Imported AFTER the mock so the component binds the stub.
const { ToolLauncher } = await import("@/components/command/tool-launcher");

const TOOLS = fixture.tools as unknown as CatalogTool[];

function tool(qualified: string): CatalogTool {
  const found = TOOLS.find((t) => t.qualified_name === qualified);
  if (!found) throw new Error(`fixture missing ${qualified}`);
  return found;
}

function launch(qualified: string) {
  return render(<ToolLauncher tool={tool(qualified)} onBack={vi.fn()} />);
}

const submit = () => fireEvent.click(screen.getByRole("button", { name: "Run" }));

function fill(name: string, value: string) {
  fireEvent.change(document.querySelector(`#arg-${name}`)!, { target: { value } });
}

beforeEach(() => {
  dispatch.mockClear();
  actionState = { pending: false, error: null, result: null, succeeded: false };
});

describe("ToolLauncher builds the ActionRef", () => {
  it("dispatches {brick, tool, args} with coerced form values", () => {
    launch("cache_set");
    fill("key", "greeting");
    fill("value", "hello");
    submit();

    expect(dispatch).toHaveBeenCalledTimes(1);
    const [action, args] = dispatch.mock.calls[0] as unknown as [
      Record<string, unknown>, Record<string, unknown>,
    ];
    expect(action.brick).toBe("cache");
    expect(action.tool).toBe("cache_set");
    expect(args).toEqual({ key: "greeting", value: "hello" });
    // Blank optional omitted, so the server applies its own default.
    expect(args).not.toHaveProperty("ttl_seconds");
  });

  it("uses qualified_name, NOT the brick-local name", () => {
    // `telemetry_record_log` is the discriminating case: name=`record_log`,
    // qualified_name=`telemetry_record_log`. `cache_set` cannot catch a
    // regression here because for the cache brick the two are identical.
    launch("telemetry_record_log");
    fill("body", "ping");
    submit();

    const [action] = dispatch.mock.calls[0] as unknown as [Record<string, unknown>];
    expect(action.brick).toBe("telemetry");
    expect(action.tool).toBe("telemetry_record_log");
    expect(action.tool).not.toBe("record_log");
  });

  it("carries an enum's preselected value through to the args", () => {
    launch("telemetry_record_log");
    fill("body", "ping");
    submit();

    const [, args] = dispatch.mock.calls[0] as unknown as [unknown, Record<string, unknown>];
    expect(args).toEqual({ severity: "DEBUG", body: "ping" });
  });

  it("coerces a numeric param to a number, not a string", () => {
    launch("cache_set");
    fill("key", "k");
    fill("value", "v");
    fill("ttl_seconds", "30");
    submit();

    const [, args] = dispatch.mock.calls[0] as unknown as [unknown, Record<string, unknown>];
    expect(args.ttl_seconds).toBe(30);
  });

  it("submits a zero-argument tool with an empty args object", () => {
    launch("cache_stats");
    submit();

    const [action, args] = dispatch.mock.calls[0] as unknown as [
      Record<string, unknown>, Record<string, unknown>,
    ];
    expect(action.tool).toBe("cache_stats");
    expect(args).toEqual({});
  });

  it("refuses to dispatch while a required param is blank", () => {
    launch("cache_set");
    fill("key", "k"); // `value` still empty
    submit();
    expect(dispatch).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Run" })).toHaveProperty("disabled", true);
  });
});

describe("ToolLauncher shows the resolved call before submit", () => {
  it("renders brick, qualified tool and live args, with no dispatch", () => {
    launch("cache_set");
    fill("key", "greeting");
    fill("value", "hello");

    const preview = screen.getByTestId("resolved-call").textContent ?? "";
    expect(preview).toContain("cache");
    expect(preview).toContain("cache_set");
    expect(preview).toContain("greeting");
    expect(preview).toContain("hello");
    expect(dispatch).not.toHaveBeenCalled();
  });

  it("names the params still blocking submit", () => {
    launch("cache_set");
    expect(screen.getByRole("status").textContent).toContain("key, value");
  });
});

describe("ToolLauncher surfaces the outcome", () => {
  it("renders a dispatch error rather than swallowing it", () => {
    actionState = { pending: false, error: "boom", result: null, succeeded: false };
    launch("cache_stats");
    expect(screen.getByTestId("action-error").textContent).toContain("boom");
  });

  it("renders the result once the dispatch succeeds", () => {
    actionState = { pending: false, error: null, result: { hits: 3 }, succeeded: true };
    launch("cache_stats");
    expect(screen.getByTestId("action-result").textContent).toContain("\"hits\": 3");
  });

  it("disables submit while pending", () => {
    actionState = { pending: true, error: null, result: null, succeeded: false };
    launch("cache_stats");
    const run = screen.getByRole("button", { name: "Running…" });
    expect(run).toHaveProperty("disabled", true);
  });
});
