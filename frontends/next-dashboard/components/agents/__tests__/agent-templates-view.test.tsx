import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(), listIds: vi.fn(), read: vi.fn(), save: vi.fn(), remove: vi.fn(),
  fork: vi.fn(), reset: vi.fn(), legacyAvailable: vi.fn(), legacyForkAvailable: vi.fn(), caps: vi.fn(),
  personas: [
    { id: "builtin", name: "Built in", description: "Core", model: "openrouter/a" },
    { id: "user-one", name: "User one", description: "Custom", model: "openrouter/b" },
  ],
}));
vi.mock("@/lib/hooks/use-mcp-connection", () => ({ useMcpConnection: () => ({ ready: true }) }));
vi.mock("@/lib/hooks/use-personas", () => ({ usePersonas: () => ({
  personas: mocks.personas, loading: false, error: null, refresh: mocks.refresh,
}) }));
vi.mock("../agent-template-api", () => ({
  personaAuthoringAvailable: (...args: unknown[]) => mocks.legacyAvailable(...args),
  personaForkAvailable: (...args: unknown[]) => mocks.legacyForkAvailable(...args),
  listUserTemplateIds: (...args: unknown[]) => mocks.listIds(...args),
  readUserTemplate: (...args: unknown[]) => mocks.read(...args),
  saveUserTemplate: (...args: unknown[]) => mocks.save(...args),
  deleteUserTemplate: (...args: unknown[]) => mocks.remove(...args),
  forkTemplate: (...args: unknown[]) => mocks.fork(...args),
  resetTemplate: (...args: unknown[]) => mocks.reset(...args),
}));
vi.mock("@/lib/authoring-capabilities", async (importOriginal) => ({
  ...(await importOriginal<typeof AuthoringCapabilitiesModule>()),
  getAuthoringCapabilities: (...args: unknown[]) => mocks.caps(...args),
}));

import type * as AuthoringCapabilitiesModule from "@/lib/authoring-capabilities";
import AgentTemplatesView from "../agent-templates-view";

const LIFECYCLE = { add: false, create: false, update: false, delete: false, fork: false, reset: false };
const capabilities = (templates: Partial<typeof LIFECYCLE>, configRead = true) => ({
  config: { read: configRead, write: false },
  skills: { ...LIFECYCLE }, steering: { ...LIFECYCLE }, agent_templates: { ...LIFECYCLE, ...templates },
  roots: {
    config: { path: "/data/agent-config", source: "env" as const },
    skills: { path: "/data/agent-skills", source: "env" as const },
    steering: { path: "/data/agent-steering", source: "env" as const },
  },
});
const ALL = capabilities({ create: true, delete: true, fork: true, reset: true });

beforeEach(() => {
  mocks.refresh.mockReset(); mocks.save.mockReset().mockResolvedValue(undefined);
  mocks.remove.mockReset().mockResolvedValue(undefined); mocks.fork.mockReset().mockResolvedValue("builtin-fork");
  mocks.reset.mockReset().mockResolvedValue(undefined);
  mocks.listIds.mockReset().mockResolvedValue(["user-one"]);
  mocks.read.mockReset().mockResolvedValue({ id: "user-one", name: "User one",
    description: "Custom", model: "openrouter/b", system_prompt: "Help", tools: [], skills: [] });
  mocks.legacyAvailable.mockReset().mockResolvedValue(true);
  mocks.legacyForkAvailable.mockReset().mockResolvedValue(true);
  mocks.caps.mockReset().mockResolvedValue(ALL);
});

describe("AgentTemplatesView", () => {
  it("keeps built-ins visible and read-only, forkable when agent_templates.fork is allowed", async () => {
    render(<AgentTemplatesView />);
    await waitFor(() => expect(screen.getByText("Built-in")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Built in/ }));
    expect(screen.getByText(/Built-in templates are read-only/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
    expect(await screen.findByRole("button", { name: "Fork this template" })).toBeTruthy();
  });

  it("loads, updates, and deletes a user template", async () => {
    render(<AgentTemplatesView />);
    await waitFor(() => expect(screen.getByText("User template")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /User one/ }));
    await waitFor(() => expect(mocks.read).toHaveBeenCalledWith("user-one"));
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Updated" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
      id: "user-one", description: "Updated", system_prompt: "Help",
    })));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith("user-one"));
  });

  it("creates a new user template when agent_templates.create is allowed", async () => {
    render(<AgentTemplatesView />);
    fireEvent.click(await screen.findByRole("button", { name: "New agent template" }));
    fireEvent.change(screen.getByLabelText("ID"), { target: { value: "new-agent" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "New agent" } });
    fireEvent.change(screen.getByLabelText("System prompt"), { target: { value: "Be helpful" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
      id: "new-agent", name: "New agent", system_prompt: "Be helpful",
    })));
  });

  it("names the variable and keeps registry reads when create is operator-denied", async () => {
    mocks.caps.mockResolvedValue(capabilities({}));
    render(<AgentTemplatesView />);
    expect(await screen.findByText(/FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES=create/)).toBeTruthy();
    expect(screen.getByText("Built in")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "New agent template" })).toBeNull();
  });

  it("shows Delete but not Save on a user template when only agent_templates.delete is allowed", async () => {
    mocks.caps.mockResolvedValue(capabilities({ delete: true }));
    render(<AgentTemplatesView />);
    await waitFor(() => expect(screen.getByText("User template")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /User one/ }));
    await waitFor(() => expect(mocks.read).toHaveBeenCalledWith("user-one"));
    expect(await screen.findByRole("button", { name: "Delete" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("gates the fork affordance on agent_templates.fork", async () => {
    mocks.caps.mockResolvedValue(capabilities({ create: true }));
    render(<AgentTemplatesView />);
    await waitFor(() => expect(screen.getByText("Built-in")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Built in/ }));
    expect(await screen.findByText(/FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES=fork/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Fork this template" })).toBeNull();
  });

  it("does not list user templates and names config=read when config.read is denied", async () => {
    mocks.caps.mockResolvedValue(capabilities({ create: true }, false));
    render(<AgentTemplatesView />);
    expect(await screen.findByText(/FACTORY_AGENT_AUTHORING_CONFIG=read/)).toBeTruthy();
    expect(mocks.listIds).not.toHaveBeenCalled();
    expect(screen.getByText("Built in")).toBeTruthy();
  });

  it("reports an unavailable capability probe without hiding the registry", async () => {
    mocks.caps.mockRejectedValue(new Error("agent_authoring_capabilities failed"));
    render(<AgentTemplatesView />);
    expect(await screen.findByText("Agent authoring unavailable")).toBeTruthy();
    expect(screen.getByText("Built in")).toBeTruthy();
  });

  it("row 33 (feature-map): forks a built-in into an editable copy", async () => {
    render(<AgentTemplatesView />);
    await waitFor(() => expect(screen.getByText("Built-in")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Built in/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Fork this template" }));
    await waitFor(() => expect(mocks.fork).toHaveBeenCalledWith("builtin", "builtin-fork"));
  });

  it("row 33 (feature-map): resets a forked template's local edits", async () => {
    render(<AgentTemplatesView />);
    await waitFor(() => expect(screen.getByText("User template")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /User one/ }));
    await waitFor(() => expect(mocks.read).toHaveBeenCalledWith("user-one"));
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    await waitFor(() => expect(mocks.reset).toHaveBeenCalledWith("user-one"));
  });
});
