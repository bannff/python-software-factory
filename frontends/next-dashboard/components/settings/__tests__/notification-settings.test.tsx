import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
const mocks = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@/lib/api", () => ({ callTool: mocks.call }));
import {
  getNotificationPreferences, listNotificationChannels,
} from "../notification-settings-api";
import NotificationSettingsPanel from "../notification-settings-panel";

const wrap = (data: unknown) => ({ tool: "notification", result: { ok: true, data } });
const channels = [{ id: "in-app", type: "console", name: "In app", enabled: true }];
const preferences = (revision = 1) => ({
  global_muted: false, muted_kinds: [], priority_overrides: {}, revision,
});

function successfulCalls() {
  mocks.call.mockImplementation((tool: string, args?: unknown) => {
    if (tool === "notification_get_channel_registry") return Promise.resolve(wrap({ channels }));
    if (tool === "notification_get_preferences") return Promise.resolve(wrap(preferences()));
    if (tool === "notification_update_preferences") return Promise.resolve(wrap({
      ...(args as object), revision: 2,
    }));
    throw new Error(`unexpected ${tool}`);
  });
}

beforeEach(() => { mocks.call.mockReset(); });

describe("Notification Settings", () => {
  it("parses sanitized channels and owner preferences", async () => {
    successfulCalls();
    await expect(listNotificationChannels()).resolves.toEqual(channels);
    await expect(getNotificationPreferences()).resolves.toEqual({
      globalMuted: false, mutedKinds: [], priorityOverrides: {}, revision: 1,
    });
  });

  it("renders event controls and saves mute with revision CAS", async () => {
    successfulCalls();
    render(<NotificationSettingsPanel />);
    expect(await screen.findByText("Schedule auto-paused")).toBeTruthy();
    expect(screen.getByText("In app")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Mute Schedule auto-paused"));
    await waitFor(() => expect(mocks.call).toHaveBeenCalledWith(
      "notification_update_preferences", {
        global_muted: false, muted_kinds: ["scheduler_auto_paused"],
        priority_overrides: {}, expected_revision: 1,
      }));
    expect(screen.queryByText(/controls are not available/)).toBeNull();
  });

  it("refetches current values after a CAS conflict", async () => {
    let reads = 0;
    mocks.call.mockImplementation((tool: string) => {
      if (tool === "notification_get_channel_registry") return Promise.resolve(wrap({ channels }));
      if (tool === "notification_get_preferences") {
        reads += 1; return Promise.resolve(wrap(preferences(reads)));
      }
      if (tool === "notification_update_preferences") return Promise.reject(new Error("conflict"));
      throw new Error(`unexpected ${tool}`);
    });
    render(<NotificationSettingsPanel />);
    const globalMute = await screen.findByLabelText("Mute all event delivery");
    fireEvent.click(globalMute);
    await waitFor(() => expect(reads).toBe(2));
    expect((await screen.findByRole("alert")).textContent).toContain("could not be saved");
  });
});

