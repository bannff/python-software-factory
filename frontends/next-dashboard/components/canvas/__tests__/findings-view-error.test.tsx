import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = { findings: [] as unknown[], error: null as string | null };
const notify = vi.fn();
vi.mock("@/lib/hooks/use-findings", () => ({
  useFindingsLoad: () => ({ findings: state.findings, error: state.error }),
  notifyFindingsChanged: () => notify(),
}));
vi.mock("@/lib/copilotkit/a2ui-canvas-slots", () => ({ usePaintedComponents: () => [] }));

import FindingsView from "../findings-view";

const view = () => render(<FindingsView steps={[]} toolCalls={[]} agentState={{}} />);

beforeEach(() => { state.findings = []; state.error = null; notify.mockReset(); });

describe("FindingsView when the read fails", () => {
  it("says findings are unavailable instead of claiming there are none", () => {
    state.error = "Tool request failed";
    view();
    expect(screen.getByText(/findings are unavailable/i)).toBeTruthy();
    expect(screen.queryByText("No findings yet")).toBeNull();
  });

  it("never shows the raw error text or a tool code", () => {
    state.error = "tool_execution_failed";
    view();
    expect(screen.queryByText(/tool_execution_failed/)).toBeNull();
  });

  it("offers a retry that reloads", () => {
    state.error = "x";
    view();
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(notify).toHaveBeenCalledTimes(1);
  });

  it("still says 'No findings yet' when the read worked and nothing is there", () => {
    view();
    expect(screen.getByText("No findings yet")).toBeTruthy();
  });
});
