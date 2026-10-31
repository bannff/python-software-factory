import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it } from "vitest";
import { MetricsNavigationActions } from "@/components/canvas/metrics-navigation-actions";
import { useWorkbenchContext, WorkbenchProvider } from "@/lib/workbench-context";
import type { NavigationRef } from "@/lib/types";

const REF: NavigationRef = {
  version: "v1",
  surface: "graph",
  target_ref: "entity-1",
  label: "Entity 1",
  graph_selected_ref: "entity-1",
  graph_context: { query_ref: "entity-1", neighborhood_limit: 20 },
  focus_origin: {
    token: "graph-open-metrics:entity-1", surface: "graph", control: "open-metrics",
  },
};

function Harness({
  onRestore,
}: { onRestore?: (ref: NavigationRef) => void }) {
  const workbench = useWorkbenchContext();
  useEffect(() => {
    if (onRestore && workbench.graphRestoreRequest) onRestore(workbench.graphRestoreRequest);
  }, [onRestore, workbench.graphRestoreRequest]);
  return (
    <>
      <button onClick={() => workbench.openMetrics(REF)}>seed metrics</button>
      <button onClick={() => workbench.returnFromMetrics()}>return</button>
      <button onClick={() => workbench.openRelatedGraph()}>related</button>
      <button onClick={workbench.toggleTerminal}>terminal</button>
      <output data-testid="terminal-open">{String(workbench.terminalOpen)}</output>
      <output data-testid="active-view">{workbench.activeView}</output>
      <output data-testid="navigation-ref">
        {JSON.stringify(workbench.navigationRef)}
      </output>
      <output data-testid="restore-request">
        {JSON.stringify(workbench.graphRestoreRequest)}
      </output>
    </>
  );
}

function renderWorkbench(onRestore?: (ref: NavigationRef) => void) {
  return render(
    <WorkbenchProvider>
      <Harness onRestore={onRestore} />
      <MetricsNavigationActions />
    </WorkbenchProvider>,
  );
}

describe("canonical workbench navigation", () => {
  it("preserves the exact ref through Metrics and related Graph", () => {
    renderWorkbench();
    fireEvent.click(screen.getByRole("button", { name: "seed metrics" }));
    expect(screen.getByTestId("active-view").textContent).toBe("metrics");
    expect(JSON.parse(screen.getByTestId("navigation-ref").textContent ?? "null")).toEqual(REF);

    fireEvent.click(screen.getByRole("button", { name: "related" }));
    expect(screen.getByTestId("active-view").textContent).toBe("graph");
    expect(JSON.parse(screen.getByTestId("restore-request").textContent ?? "null")).toEqual(REF);
    expect(screen.getByText("Opened related Graph for Entity 1.")).toBeTruthy();
  });

  it("requests the same selected Graph item when returning from Metrics", () => {
    renderWorkbench();
    fireEvent.click(screen.getByRole("button", { name: "seed metrics" }));
    fireEvent.click(screen.getByRole("button", { name: "return" }));
    expect(screen.getByTestId("active-view").textContent).toBe("graph");
    expect(JSON.parse(screen.getByTestId("restore-request").textContent ?? "null")).toEqual(REF);
  });

  it("disables unavailable actions with explanatory text", () => {
    renderWorkbench();
    expect((screen.getByRole("button", { name: "Return to originating surface" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Open related graph" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/no originating navigation reference/i)).toBeTruthy();
    expect(screen.getByText(/no bounded Graph context/i)).toBeTruthy();
  });

  it("creates a fresh equivalent restore request for each retry", () => {
    const requests: NavigationRef[] = [];
    renderWorkbench((ref) => requests.push(ref));
    fireEvent.click(screen.getByRole("button", { name: "seed metrics" }));
    fireEvent.click(screen.getByRole("button", { name: "return" }));
    fireEvent.click(screen.getByRole("button", { name: "return" }));

    expect(requests).toHaveLength(2);
    expect(requests[0]).not.toBe(requests[1]);
    expect(requests[0]).toEqual(requests[1]);
  });

  it("toggles the global Terminal dock without changing the active view", () => {
    renderWorkbench();
    expect(screen.getByTestId("terminal-open").textContent).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "terminal" }));
    expect(screen.getByTestId("terminal-open").textContent).toBe("true");
    expect(screen.getByTestId("active-view").textContent).toBe("welcome");
  });

  it("opens the Terminal dock from an explicit deep link", async () => {
    window.history.pushState({}, "", "/?terminal=1");
    renderWorkbench();
    await waitFor(() => expect(screen.getByTestId("terminal-open").textContent).toBe("true"));
  });
});
