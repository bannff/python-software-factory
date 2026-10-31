import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const registrations = new Map<string, { handler: (args: Record<string, unknown>) => Promise<Record<string, unknown>> }>();
vi.mock("@copilotkit/react-core/v2", () => ({
  useFrontendTool: (config: { name: string; handler: (args: Record<string, unknown>) => Promise<Record<string, unknown>> }) => registrations.set(config.name, config),
  useHumanInTheLoop: vi.fn(),
  useRenderTool: vi.fn(),
}));
// `<FrontendTools>` mounts OperationsNavigationTools, which calls useRouter();
// a bare render has no app-router context (same mock as operations-navigation.test.tsx).
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { FrontendTools } from "@/lib/copilotkit/frontend-tools";
import { WorkbenchProvider, useWorkbenchContext } from "@/lib/workbench-context";

function ViewProbe() {
  return <output data-testid="active-view">{useWorkbenchContext().activeView}</output>;
}

const FULL_ID = "workflow-run-01JZ8Q2V0F7PA4M6KG9X3N5B8C";

beforeEach(() => {
  registrations.clear();
  window.history.replaceState({}, "", "/?keep=1");
});

describe("fe_focus_run", () => {
  it("registers explicitly, validates at runtime, and only changes focus", async () => {
    render(<WorkbenchProvider><FrontendTools /><ViewProbe /></WorkbenchProvider>);
    expect(document.querySelector("[data-testid='active-view']")?.textContent).toBe("welcome");
    const tool = registrations.get("fe_focus_run");
    expect(tool).toBeDefined();
    await expect(tool!.handler({ run_id: "   " })).resolves.toMatchObject({ success: false });
    expect(new URL(window.location.href).searchParams.has("run")).toBe(false);
    await act(async () => { await tool!.handler({ run_id: FULL_ID }); });
    expect(new URL(window.location.href).searchParams.get("run")).toBe(FULL_ID);
    expect(new URL(window.location.href).searchParams.get("keep")).toBe("1");
    expect(document.querySelector("[data-testid='active-view']")?.textContent).toBe("welcome");
  });
});
