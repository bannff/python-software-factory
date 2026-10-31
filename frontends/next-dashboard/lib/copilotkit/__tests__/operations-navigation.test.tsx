import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const registrations = new Map<string, { handler: (args: { id: string }) => Promise<Record<string, unknown>> }>();
const push = vi.fn();
const switchView = vi.fn();
vi.mock("@copilotkit/react-core/v2", () => ({
  useFrontendTool: (config: { name: string; handler: (args: { id: string }) => Promise<Record<string, unknown>> }) => registrations.set(config.name, config),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/workbench-context", () => ({ useWorkbenchContext: () => ({ switchView }) }));

import { OperationsNavigationTools } from "../operations-navigation-tools";

beforeEach(() => { registrations.clear(); push.mockReset(); switchView.mockReset(); });

describe("Operations navigation frontend tools", () => {
  it("registers exact session, schedule, and lesson tools", () => {
    render(<OperationsNavigationTools />);
    expect([...registrations.keys()]).toEqual([
      "fe_navigate_session", "fe_navigate_schedule", "fe_navigate_lesson",
    ]);
  });

  it.each([
    ["session", "sessions"], ["schedule", "schedules"], ["lesson", "lessons"],
  ] as const)("navigates one exact %s id", async (kind, view) => {
    render(<OperationsNavigationTools />);
    const result = await registrations.get(`fe_navigate_${kind}`)!.handler({ id: "item-1" });
    expect(result).toMatchObject({ success: true, view, id: "item-1" });
    expect(switchView).toHaveBeenCalledWith(view);
    expect(push).toHaveBeenCalledWith(`/${view}/item-1`);
  });

  it("refuses path-like ids without navigation", async () => {
    render(<OperationsNavigationTools />);
    const result = await registrations.get("fe_navigate_session")!.handler({ id: "../escape" });
    expect(result.success).toBe(false);
    expect(push).not.toHaveBeenCalled();
  });
});
