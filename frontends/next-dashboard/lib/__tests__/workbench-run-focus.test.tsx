import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { WorkbenchProvider, useWorkbenchContext } from "@/lib/workbench-context";

const FULL_ID = "workflow-run-01JZ8Q2V0F7PA4M6KG9X3N5B8C";

function Harness() {
  const workbench = useWorkbenchContext();
  return <><button onClick={() => workbench.focusRun(FULL_ID)}>focus</button><button onClick={workbench.clearRunFocus}>clear</button><output data-testid="run">{workbench.focusedRunId ?? "none"}</output></>;
}
function mount() { return render(<WorkbenchProvider><Harness /></WorkbenchProvider>); }

beforeEach(() => window.history.replaceState({}, "", "/?keep=1"));

describe("central workbench run focus", () => {
  it("initializes from a full deep-link ID and preserves unrelated query params", () => {
    window.history.replaceState({}, "", `/?keep=1&run=${FULL_ID}`);
    mount();
    expect(screen.getByTestId("run").textContent).toBe(FULL_ID);
    expect(new URL(window.location.href).searchParams.get("keep")).toBe("1");
  });

  it("focuses and clears through the URL without truncating the ID", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "focus" }));
    expect(screen.getByTestId("run").textContent).toBe(FULL_ID);
    expect(new URL(window.location.href).searchParams.get("run")).toBe(FULL_ID);
    expect(new URL(window.location.href).searchParams.get("keep")).toBe("1");
    fireEvent.click(screen.getByRole("button", { name: "clear" }));
    expect(screen.getByTestId("run").textContent).toBe("none");
    expect(new URL(window.location.href).searchParams.has("run")).toBe(false);
  });

  it("synchronizes focus on popstate", () => {
    mount();
    window.history.pushState({}, "", `/?keep=1&run=${FULL_ID}`);
    act(() => window.dispatchEvent(new PopStateEvent("popstate")));
    expect(screen.getByTestId("run").textContent).toBe(FULL_ID);
    window.history.pushState({}, "", "/?keep=1");
    act(() => window.dispatchEvent(new PopStateEvent("popstate")));
    expect(screen.getByTestId("run").textContent).toBe("none");
  });
});
