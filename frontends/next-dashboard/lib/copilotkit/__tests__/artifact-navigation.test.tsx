import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

const registrations = new Map<string, { handler: (args: unknown) => Promise<Record<string, unknown>> }>();
const switchView = vi.fn();
vi.mock("@copilotkit/react-core/v2", () => ({
  useFrontendTool: (config: { name: string; handler: (args: unknown) => Promise<Record<string, unknown>> }) => registrations.set(config.name, config),
}));
vi.mock("@/lib/workbench-context", () => ({
  useWorkbenchContext: () => ({ switchView }),
}));

import { useArtifactNavigationTool } from "../artifact-navigation-tool";

function Harness() { useArtifactNavigationTool(); return null; }

describe("fe_navigate_artifacts", () => {
  it("navigates by stable slug without mutating state", async () => {
    render(<Harness />);
    const result = await registrations.get("fe_navigate_artifacts")!.handler({ slug: "release-notes" });
    expect(result).toEqual({ success: true, path: "/artifacts/release-notes", slug: "release-notes" });
    expect(window.location.pathname).toBe("/artifacts/release-notes");
    expect(switchView).toHaveBeenCalledWith("artifacts");
  });

  it("refuses malformed slugs", async () => {
    render(<Harness />);
    const result = await registrations.get("fe_navigate_artifacts")!.handler({ slug: "../escape" });
    expect(result.success).toBe(false);
  });
});
