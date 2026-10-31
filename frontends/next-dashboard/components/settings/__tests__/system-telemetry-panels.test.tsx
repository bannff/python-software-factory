import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ health: {} as Record<string, unknown> }));
vi.mock("@/lib/hooks/use-health", () => ({ useHealth: () => mocks.health }));

import { SystemPanel } from "../system-panel";
import { TelemetryPanel } from "../telemetry-panel";

describe("SystemPanel (row 105) + TelemetryPanel (row 106)", () => {
  it("SystemPanel shows gateway, status, and service census", () => {
    mocks.health = {
      connected: true, status: "healthy", gateway: "http://127.0.0.1:8000",
      totalTools: 816, brickCount: 45, healthyBricks: 45, timeline: null, lastChecked: Date.now(),
    };
    render(<SystemPanel />);
    expect(screen.getByText("online")).toBeTruthy();
    expect(screen.getByText("http://127.0.0.1:8000")).toBeTruthy();
    expect(screen.getByText("816")).toBeTruthy();
    expect(screen.getByText("45")).toBeTruthy();
  });

  it("TelemetryPanel shows live transport and history backend", () => {
    mocks.health = {
      timeline: { live: { available: true, transport: "sse" }, history: { available: true, persistent: true, backend: "sqlite", reason: null } },
    };
    render(<TelemetryPanel />);
    expect(screen.getByText("sse")).toBeTruthy();
    expect(screen.getByText(/sqlite · persistent/)).toBeTruthy();
  });

  it("TelemetryPanel degrades when the timeline is unavailable", () => {
    mocks.health = { timeline: { live: { available: false, transport: "" }, history: { available: false, persistent: false, backend: "", reason: "not configured" } } };
    render(<TelemetryPanel />);
    expect(screen.getByText("unavailable")).toBeTruthy();
    expect(screen.getByText("not configured")).toBeTruthy();
  });
});
