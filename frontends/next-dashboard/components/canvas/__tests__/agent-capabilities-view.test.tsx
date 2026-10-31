import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ requested: null as string | null }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(mocks.requested ? `tab=${mocks.requested}` : ""),
}));
vi.mock("@/components/connections/connections-view", () => ({ default: () => <div>Connections content</div> }));
vi.mock("@/components/hooks/hooks-view", () => ({ default: () => <div>Hooks content</div> }));
vi.mock("@/components/crews/crews-view", () => ({ default: () => <div>Crews content</div> }));
vi.mock("@/components/artifacts/artifacts-view", () => ({ default: () => <div>Artifacts content</div> }));
vi.mock("@/components/operations/schedules/schedules-view", () => ({ default: () => <div>Schedules content</div> }));
vi.mock("@/components/operations/lessons/lessons-view", () => ({ default: () => <div>Lessons content</div> }));
vi.mock("@/components/operations/memory/memory-view", () => ({ default: () => <div>Memory content</div> }));
vi.mock("@/components/operations/knowledge/knowledge-view", () => ({ default: () => <div>Knowledge content</div> }));
vi.mock("@/components/operations/workflows/workflow-library-view", () => ({ default: () => <div>Workflows content</div> }));
vi.mock("@/components/prompts/prompts-view", () => ({ default: () => <div>Prompts content</div> }));
vi.mock("@/components/operations/projects/projects-view", () => ({ default: () => <div>Projects content</div> }));
vi.mock("@/components/skills/skills-view", () => ({ default: () => <div>Skills content</div> }));
vi.mock("@/components/steering/steering-view", () => ({ default: () => <div>Steering content</div> }));

import AgentCapabilitiesView from "../agent-capabilities-view";

beforeEach(() => {
  mocks.requested = null;
  window.history.pushState({}, "", "/capabilities");
});

describe("AgentCapabilitiesView", () => {
  it("exposes the exact binding capability inventory", () => {
    render(<AgentCapabilitiesView />);
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Crews", "Agent Templates", "Connections", "Skills", "Steering",
      "Hooks", "Prompts", "Projects", "Schedules", "Artifacts", "Memory",
      "Knowledge", "Workflows", "Lessons",
    ]);
    expect(screen.getByText("Crews content")).toBeTruthy();
  });

  it("renders working child surfaces and updates the stable tab URL", () => {
    render(<AgentCapabilitiesView />);
    fireEvent.click(screen.getByRole("tab", { name: "Schedules" }));
    expect(screen.getByText("Schedules content")).toBeTruthy();
    expect(window.location.search).toBe("?tab=schedules");
  });

  it("renders every owner-priority capability child", () => {
    render(<AgentCapabilitiesView />);
    fireEvent.click(screen.getByRole("tab", { name: "Connections" }));
    expect(screen.getByText("Connections content")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Skills" }));
    expect(screen.getByText("Skills content")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Steering" }));
    expect(screen.getByText("Steering content")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Hooks" }));
    expect(screen.getByText("Hooks content")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Prompts" }));
    expect(screen.getByText("Prompts content")).toBeTruthy();
  });

  it("accepts a valid deep-linked tab", () => {
    mocks.requested = "lessons";
    render(<AgentCapabilitiesView />);
    expect(screen.getByRole("tab", { name: "Lessons" }).getAttribute("aria-selected"))
      .toBe("true");
    expect(screen.getByText("Lessons content")).toBeTruthy();
  });
});
