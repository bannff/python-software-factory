import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ health: {} as Record<string, unknown> }));
vi.mock("@/lib/hooks/use-health", () => ({ useHealth: () => mocks.health }));

import { McpPoolPanel } from "../mcp-pool-panel";

describe("McpPoolPanel (row 108, feature-map)", () => {
  it("shows connection status, counts, and per-brick health", () => {
    mocks.health = {
      connected: true, status: "healthy", totalTools: 816, brickCount: 45, healthyBricks: 45,
      bricks: { session: { healthy: true, error: null }, memory: { healthy: true, error: null } },
      lastChecked: Date.now(),
    };
    render(<McpPoolPanel />);
    expect(screen.getByText("connected")).toBeTruthy();
    expect(screen.getByText(/45 \/ 45 healthy/)).toBeTruthy();
    expect(screen.getByText("816")).toBeTruthy();
    expect(screen.getByText("session")).toBeTruthy();
  });

  it("surfaces an unhealthy brick's error", () => {
    mocks.health = {
      connected: false, status: "unhealthy", totalTools: null, brickCount: 2, healthyBricks: 1,
      bricks: { graph: { healthy: false, error: "connection refused" } },
      lastChecked: Date.now(),
    };
    render(<McpPoolPanel />);
    expect(screen.getByText("unhealthy")).toBeTruthy();
    expect(screen.getByText("connection refused")).toBeTruthy();
  });
});
