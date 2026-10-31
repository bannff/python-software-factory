import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ callTool: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: (...a: unknown[]) => mocks.callTool(...a) }));

import BrowserSettingsPanel from "../browser-settings-panel";

const ok = (data: Record<string, unknown>) => ({ structuredContent: { ok: true, data } });
const STATUS = { engine: "mock", available_engines: ["mock", "cdp"], chrome_path: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  chrome_found: true, websockets_available: true, change_hint: "Set FACTORY_BROWSER_ADAPTER=cdp|mock in the API environment and restart." };

beforeEach(() => { mocks.callTool.mockReset(); });

describe("Settings → Browser engine", () => {
  it("reports the effective engine truthfully and warns when it is the mock", async () => {
    mocks.callTool.mockResolvedValueOnce(ok(STATUS));
    render(<BrowserSettingsPanel />);
    expect(await screen.findByText("Mock — no real browser")).toBeTruthy();
    expect(screen.getByText(/placeholder results until the engine is set to CDP/)).toBeTruthy();
    expect(screen.getByText(/FACTORY_BROWSER_ADAPTER=cdp/)).toBeTruthy();
    expect(screen.getByText("available")).toBeTruthy();
  });

  it("shows CDP as the real engine and runs the smoke test", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({ ...STATUS, engine: "cdp" }))
      .mockResolvedValueOnce(ok({ engine: "cdp", ok: true, browser_type: "cdp", error: null, elapsed_ms: 812 }));
    render(<BrowserSettingsPanel />);
    expect(await screen.findByText("System Chrome (CDP)")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Test engine/ }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("browser_engine_smoke"));
    expect((await screen.findByRole("status")).textContent).toContain("cdp session in 812 ms");
  });

  it("surfaces a failed smoke test with the engine's own error", async () => {
    mocks.callTool.mockResolvedValueOnce(ok({ ...STATUS, chrome_found: false, chrome_path: null }))
      .mockResolvedValueOnce(ok({ engine: "cdp", ok: false, browser_type: null, error: "FileNotFoundError: chromium", elapsed_ms: 3 }));
    render(<BrowserSettingsPanel />);
    expect(await screen.findByText("not found")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Test engine/ }));
    expect((await screen.findByRole("status")).textContent).toContain("FileNotFoundError: chromium");
  });
});
