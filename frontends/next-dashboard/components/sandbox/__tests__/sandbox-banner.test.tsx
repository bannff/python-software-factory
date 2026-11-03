import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => callTool(...a) }));

import { SandboxBanner } from "../sandbox-banner";

const summary = (adapter: unknown) => ({ schema_version: "v1", ok: true, data: { overview: { environments: 0, adapter } } });
beforeEach(() => { callTool.mockReset(); });

describe("SandboxBanner", () => {
  it("says plainly that nothing real runs when the adapter is the mock", async () => {
    callTool.mockResolvedValue(summary("mock"));
    render(<SandboxBanner />);
    const note = await screen.findByRole("note");
    expect(note.textContent).toMatch(/simulated environment/i);
    expect(note.textContent).toMatch(/no containers run/i);
    expect(callTool).toHaveBeenCalledWith("sandbox_get_dashboard_summary");
  });

  it("shows nothing for a real adapter", async () => {
    callTool.mockResolvedValue(summary("docker"));
    render(<SandboxBanner />);
    await waitFor(() => expect(callTool).toHaveBeenCalled());
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("shows nothing when the summary cannot be read, rather than guessing", async () => {
    callTool.mockImplementation(async () => { throw new Error("tool_execution_failed"); });
    render(<SandboxBanner />);
    await waitFor(() => expect(callTool).toHaveBeenCalled());
    expect(screen.queryByRole("note")).toBeNull();
  });
});
