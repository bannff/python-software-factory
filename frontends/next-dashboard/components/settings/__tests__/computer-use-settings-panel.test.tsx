import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import ComputerUseSettingsPanel from "../computer-use-settings-panel";

const ok = (data: Record<string, unknown>) => ({ structuredContent: { ok: true, data } });
const UNMOUNTED = { platform_supported: true, mounted: false, server_name: null, tool_names: [], preset_name: "computer",
  preset_command: "kirocrew", preset_args: ["mcp-computer"], preset_command_found: true,
  preset_command_path: "/Users/o/.local/bin/kirocrew", accessibility_hint: "macOS grants Accessibility to the KiroCrew gateway." };
const SERVER = { name: "computer", transport: "stdio", command: "kirocrew", args: ["mcp-computer"], cwd: null, env: {},
  url: null, headers: {}, enabled: true, mounted: true, unresolved_env: [], tools_count: 10, revision: 1 };

beforeEach(() => { mocks.callTool.mockReset(); });

describe("Settings → Computer Use", () => {
  it("shows not-mounted truthfully and registers the preset through Connections in one click", async () => {
    mocks.callTool.mockResolvedValueOnce(ok(UNMOUNTED))
      .mockResolvedValueOnce(ok({ server: SERVER }))
      .mockResolvedValueOnce(ok({ ...UNMOUNTED, mounted: true, server_name: "computer",
        tool_names: ["computer.computer_click", "computer.computer_get_state"] }));
    render(<ComputerUseSettingsPanel />);
    expect(await screen.findByText("Not mounted")).toBeTruthy();
    expect(screen.getByText(/no desktop tools until/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Register the KiroCrew computer server/ }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("connections_add_server", {
      name: "computer", spec: { transport: "stdio", command: "kirocrew", args: ["mcp-computer"], enabled: true },
    }));
    expect((await screen.findByRole("status")).textContent).toContain("Mounted 10 desktop tools as mcp-computer");
    expect(await screen.findByText("Mounted — computer (2 tools)")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Register/ })).toBeNull();
  });

  it("disables the preset when the command is not installed and explains", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({ ...UNMOUNTED, preset_command_found: false, preset_command_path: null }));
    render(<ComputerUseSettingsPanel />);
    const button = await screen.findByRole("button", { name: /Register the KiroCrew computer server/ });
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(/not found — install KiroCrew/)).toBeTruthy();
  });

  it("reports when the registered server did not mount instead of claiming success", async () => {
    mocks.callTool.mockResolvedValueOnce(ok(UNMOUNTED))
      .mockResolvedValueOnce(ok({ server: { ...SERVER, mounted: false, tools_count: 0 } }))
      .mockResolvedValueOnce(ok(UNMOUNTED));
    render(<ComputerUseSettingsPanel />);
    fireEvent.click(await screen.findByRole("button", { name: /Register/ }));
    expect((await screen.findByRole("status")).textContent).toContain("did not mount");
  });
});
