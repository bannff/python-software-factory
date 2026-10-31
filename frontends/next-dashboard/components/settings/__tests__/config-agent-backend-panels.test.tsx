import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ health: {} as Record<string, unknown>, catalog: {} as Record<string, unknown> }));
vi.mock("@/lib/hooks/use-health", () => ({ useHealth: () => mocks.health }));
vi.mock("@/lib/hooks/use-model-catalog", () => ({ useModelCatalog: () => mocks.catalog }));

import { ConfigPanel } from "../config-panel";
import { AgentBackendPanel } from "../agent-backend-panel";

describe("ConfigPanel (row 110) + AgentBackendPanel (row 111)", () => {
  it("ConfigPanel shows resolved gateway + model providers and a read-only note", () => {
    mocks.health = { gateway: "http://127.0.0.1:8000", status: "healthy" };
    mocks.catalog = { groups: [{ provider: "openrouter", models: [{ model_id: "a" }, { model_id: "b" }] }] };
    render(<ConfigPanel />);
    expect(screen.getByText("http://127.0.0.1:8000")).toBeTruthy();
    expect(screen.getByText("openrouter")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText(/not editable from this page/i)).toBeTruthy();
  });

  it("AgentBackendPanel states the LangGraph/MCP-v2 harness and live status", () => {
    mocks.health = { connected: true, status: "healthy" };
    render(<AgentBackendPanel />);
    expect(screen.getByText("live")).toBeTruthy();
    expect(screen.getByText("LangChain / LangGraph")).toBeTruthy();
    expect(screen.getByText("MCP v2")).toBeTruthy();
  });
});
