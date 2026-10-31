import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import UsageSettingsPanel from "../usage-settings-panel";

const snapshot = {
  started_at: 1_700_000_000,
  llm: { interactions: 12, input_tokens: 4000, output_tokens: 1500, total_tokens: 5500, cost_usd: 0.0123, last_latency_ms: 842.3 },
  agent: { executions: 3 }, tools: { invocations: 21 }, logs: { total: 0, by_severity: {} }, errors: 1,
};

/** Real shape confirmed live: `callTool`'s own unwrap stops one level short of
 * the actual payload for this brick's structured_content nesting — so the
 * component (and this mock) must go through `unwrapToolData` on the
 * `{schema_version, ok, data}` wrapper `callTool` actually returns. */
const wrap = (data: unknown) => ({ tool: "get_metrics_summary", result: { schema_version: "v1", ok: true, data } });

beforeEach(() => { mocks.callTool.mockReset(); });

describe("UsageSettingsPanel (feature-map row 52)", () => {
  it("shows real cumulative counters from get_metrics_summary, honestly labeled as a running total not a date range", async () => {
    mocks.callTool.mockResolvedValue(wrap(snapshot));
    render(<UsageSettingsPanel />);
    expect(await screen.findByText("12")).toBeTruthy();
    expect(screen.getByText("4,000 / 1,500")).toBeTruthy();
    expect(screen.getByText("$0.0123")).toBeTruthy();
    expect(screen.getByText("21")).toBeTruthy();
    expect(screen.getByText("842 ms")).toBeTruthy();
    expect(screen.getByText(/not a calendar-range history/i)).toBeTruthy();
    expect(mocks.callTool).toHaveBeenCalledWith("get_metrics_summary", {});
  });

  it("shows a truthful unavailable state instead of fabricating zeros on a tool failure", async () => {
    mocks.callTool.mockRejectedValue(new Error("tool failed"));
    render(<UsageSettingsPanel />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/unavailable right now/i)).toBeTruthy();
  });

  it("handles a null last_latency_ms without crashing", async () => {
    mocks.callTool.mockResolvedValue(wrap({ ...snapshot, llm: { ...snapshot.llm, last_latency_ms: null } }));
    render(<UsageSettingsPanel />);
    await waitFor(() => expect(screen.getAllByText("—").length).toBeGreaterThan(0));
  });
});
