import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ list: vi.fn(), renderPrompt: vi.fn() }));
vi.mock("@/lib/hooks/use-mcp-connection", () => ({
  useMcpConnection: () => ({ ready: true, status: "connected" }),
}));
vi.mock("../prompts-api", () => ({
  listFactoryPrompts: (...args: unknown[]) => mocks.list(...args),
  renderFactoryPrompt: (...args: unknown[]) => mocks.renderPrompt(...args),
}));

import PromptsView from "../prompts-view";

const prompts = [
  { brick: "agent", name: "reason", description: "Reason about a task", arguments: [
    { name: "task", description: "Task to reason about", required: true },
  ] },
  { brick: "ui", name: "dashboard", description: "Create a dashboard", arguments: [] },
];

beforeEach(() => {
  mocks.list.mockReset().mockResolvedValue({ prompts, failedBricks: [] });
  mocks.renderPrompt.mockReset().mockResolvedValue([
    { role: "user", content: "Reason about releases" },
  ]);
});

describe("PromptsView", () => {
  it("lists registry prompts and filters without fabricating an empty state", async () => {
    render(<PromptsView />);
    expect(await screen.findByRole("button", { name: /reason/i })).toBeTruthy();
    expect(screen.getByText("2 prompts · 2 registries")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Search prompts"), { target: { value: "dashboard" } });
    expect(screen.getByRole("button", { name: /dashboard/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /reason/i })).toBeNull();
    fireEvent.change(screen.getByLabelText("Search prompts"), { target: { value: "missing" } });
    expect(screen.getByText("No matching prompts.")).toBeTruthy();
  });

  it("collects required arguments and renders the selected prompt through MCP", async () => {
    render(<PromptsView />);
    fireEvent.click(await screen.findByRole("button", { name: /reason/i }));
    const renderButton = screen.getByRole("button", { name: "Render through MCP" });
    expect(renderButton.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText(/task/i), { target: { value: "releases" } });
    expect(renderButton.hasAttribute("disabled")).toBe(false);
    fireEvent.click(renderButton);
    await waitFor(() => expect(mocks.renderPrompt).toHaveBeenCalledWith(prompts[0], { task: "releases" }));
    expect(await screen.findByText("Reason about releases")).toBeTruthy();
  });

  it("shows partial registry failures alongside usable results", async () => {
    mocks.list.mockResolvedValue({ prompts: [prompts[0]], failedBricks: ["legacy"] });
    render(<PromptsView />);
    expect(await screen.findByRole("button", { name: /reason/i })).toBeTruthy();
    expect(screen.getByText(/legacy/)).toBeTruthy();
    expect(screen.queryByText("No MCP prompts are registered.")).toBeNull();
  });
});
