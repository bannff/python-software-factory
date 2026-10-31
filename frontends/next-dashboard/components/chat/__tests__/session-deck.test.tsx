import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  sessions: [
    { session_id: "s1", thread_id: "t1", title: "Provider migration", agent_id: "companion-x-default", model: "openrouter", updated_at: new Date().toISOString(), archived_at: null, revision: 1, crew_id: "", memory_scope: "", pinned_rank: null },
    { session_id: "s2", thread_id: "t2", title: "Review telemetry", agent_id: "reviewer", model: "ollama/llama3", updated_at: new Date().toISOString(), archived_at: null, revision: 1, crew_id: "redteam-crew", memory_scope: "redteam", pinned_rank: null },
  ],
  agent: { threadId: "t1", messages: [], isRunning: false, setMessages: vi.fn() },
  core: { properties: {} as Record<string, unknown>, setProperties: vi.fn() },
  loadHistory: vi.fn(),
  defaultId: null as string | null,
  callTool: vi.fn(),
}));

vi.mock("@copilotkit/react-core/v2", () => ({
  useAgent: () => ({ agent: mocks.agent }),
  useCopilotKit: () => ({ copilotkit: mocks.core }),
  UseAgentUpdate: { OnMessagesChanged: "messages" },
}));
vi.mock("@/lib/hooks/use-session-list", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/hooks/use-session-list")>(),
  useSessionList: () => ({ sessions: mocks.sessions, loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/hooks/use-session-history", () => ({
  loadSessionHistory: (...args: unknown[]) => mocks.loadHistory(...args),
}));
vi.mock("@/lib/hooks/use-crews", () => ({
  useCrews: () => ({ defaultId: mocks.defaultId }),
}));
vi.mock("@/lib/api", () => ({
  callTool: (...args: unknown[]) => mocks.callTool(...args),
}));

vi.mock("@/lib/hooks/use-personas", () => ({
  usePersonas: () => ({ personas: [
    { id: "companion-x-default", name: "Companion X" },
    { id: "reviewer", name: "Reviewer" },
  ], loading: false, error: null, refresh: vi.fn() }),
}));
import { SessionDeck } from "../session-deck";
import { parseResolvedCrew } from "@/components/crews/crew-types";

beforeEach(() => {
  mocks.agent.threadId = "t1";
  mocks.agent.setMessages.mockReset();
  mocks.core.properties = {};
  mocks.core.setProperties.mockReset();
  mocks.defaultId = null;
  mocks.callTool.mockReset();
  mocks.loadHistory.mockReset().mockResolvedValue([
    { id: "u2", role: "user", content: "review this" },
    { id: "a2", role: "assistant", content: "reviewed" },
  ]);
  mocks.sessions.splice(0, mocks.sessions.length,
    { session_id: "s1", thread_id: "t1", title: "Provider migration", agent_id: "companion-x-default", model: "openrouter", updated_at: new Date().toISOString(), archived_at: null, revision: 1, crew_id: "", memory_scope: "", pinned_rank: null },
    { session_id: "s2", thread_id: "t2", title: "Review telemetry", agent_id: "reviewer", model: "ollama/llama3", updated_at: new Date().toISOString(), archived_at: null, revision: 1, crew_id: "redteam-crew", memory_scope: "redteam", pinned_rank: null },
  );
});

describe("SessionDeck", () => {
  it("starts collapsed with the active title and expands recent sessions", () => {
    render(<SessionDeck agentId="companion_x" />);
    const toggle = screen.getByRole("button", { name: "Show sessions" });
    expect(toggle.textContent).toContain("Provider migration");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("button", { name: /Review telemetry/ })).toBeNull();

    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Hide sessions" }).getAttribute("aria-expanded")).toBe("true");
    expect(screen.queryByText("Review telemetry")).not.toBeNull();
    expect(document.querySelector('[data-session-row="s1"]')?.getAttribute("aria-current")).toBe("true");
  });

  it("hydrates history before switching the native agent thread", async () => {
    render(<SessionDeck agentId="companion_x" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sessions" }));
    fireEvent.click(screen.getByText("Review telemetry").closest("button")!);
    expect(screen.queryByText("Loading conversation…")).not.toBeNull();
    expect(mocks.agent.threadId).toBe("t1");
    await waitFor(() => expect(mocks.agent.threadId).toBe("t2"));
    expect(mocks.loadHistory).toHaveBeenCalledWith("s2");
    expect(mocks.agent.setMessages).toHaveBeenCalledWith([
      { id: "u2", role: "user", content: "review this" },
      { id: "a2", role: "assistant", content: "reviewed" },
    ]);
    expect(screen.queryByRole("button", { name: "Show sessions" })).not.toBeNull();
  });


  it("discards a stale history load after a newer selection", async () => {
    let resolveSlow!: (messages: unknown[]) => void;
    mocks.loadHistory
      .mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSlow = resolve; }))
      .mockResolvedValueOnce([{ id: "new", role: "user", content: "current" }]);
    render(<SessionDeck agentId="companion_x" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sessions" }));
    fireEvent.click(screen.getByText("Review telemetry").closest("button")!);
    fireEvent.click(document.querySelector<HTMLButtonElement>('[data-session-row="s1"]')!);
    await waitFor(() => expect(mocks.agent.setMessages).toHaveBeenCalledWith([
      { id: "new", role: "user", content: "current" },
    ]));
    await act(async () => resolveSlow([{ id: "old", role: "user", content: "stale" }]));
    expect(mocks.agent.threadId).toBe("t1");
    expect(mocks.agent.setMessages).toHaveBeenCalledTimes(1);
  });
  it("moves focus between session rows with arrow keys", () => {
    render(<SessionDeck agentId="companion_x" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sessions" }));
    const first = document.querySelector<HTMLButtonElement>('[data-session-row="s1"]')!;
    const second = document.querySelector<HTMLButtonElement>('[data-session-row="s2"]')!;
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(document.activeElement).toBe(second);
  });

  it("restores the full binding into properties without clobbering on switch", async () => {
    mocks.core.properties = { existing_prop: "keep-me" };
    render(<SessionDeck agentId="companion_x" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sessions" }));
    fireEvent.click(screen.getByText("Review telemetry").closest("button")!);
    await waitFor(() => expect(mocks.agent.threadId).toBe("t2"));
    expect(mocks.core.setProperties).toHaveBeenCalledWith({
      existing_prop: "keep-me",
      companion_x_agent_id: "reviewer",
      companion_x_model: "ollama/llama3",
      companion_x_memory_scope: "redteam",
      companion_x_crew_id: "redteam-crew",
    });
  });

  it("starts the configured default crew through Agent resolve and Session create", async () => {
    mocks.defaultId = "redteam-crew";
    const resolvedPayload = { schema_version: "v1", ok: true, data: {
      crew_id: "redteam-crew", persona_id: "reviewer",
      model_id: "ollama/llama3", project: "/work/project",
      workspace: "main", memory_scope: "redteam",
    } };
    expect(parseResolvedCrew(resolvedPayload).crew_id).toBe("redteam-crew");
    mocks.callTool
      .mockResolvedValueOnce(resolvedPayload)
      .mockResolvedValueOnce({ schema_version: "v1", ok: true, data: { session: {
        session_id: "s-new", thread_id: "t-new", title: "New session",
        agent_id: "reviewer", model: "ollama/llama3", updated_at: new Date().toISOString(),
        archived_at: null, revision: 1, crew_id: "redteam-crew", memory_scope: "redteam",
      } } });
    render(<SessionDeck agentId="companion_x" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sessions" }));
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    await waitFor(() => expect(
      mocks.callTool.mock.calls.map((call) => call[0]),
    ).toEqual(["agent_resolve_crew", "session_create"]));
    await waitFor(() => expect(mocks.agent.threadId).toBe("t-new"));
    expect(mocks.callTool).toHaveBeenNthCalledWith(1, "agent_resolve_crew", {
      crew_id: "redteam-crew",
    });
    expect(mocks.callTool).toHaveBeenNthCalledWith(2, "session_create", expect.objectContaining({
      agent_id: "reviewer", model: "ollama/llama3", project: "/work/project",
      crew_id: "redteam-crew", memory_scope: "redteam",
    }));
    expect(mocks.core.setProperties).toHaveBeenCalledWith(expect.objectContaining({
      companion_x_agent_id: "reviewer", companion_x_model: "ollama/llama3",
      companion_x_memory_scope: "redteam", companion_x_crew_id: "redteam-crew",
    }));
  });

  it("pins a session through the shared revision-fenced action", async () => {
    mocks.callTool.mockResolvedValue({ tool: "session_set_pinned", result: {
      session: { ...mocks.sessions[1], pinned_rank: 1024, revision: 2 },
    } });
    render(<SessionDeck agentId="companion_x" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sessions" }));
    fireEvent.click(screen.getByRole("button", { name: "Pin Review telemetry" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_set_pinned", {
      session_id: "s2", pinned: true, expected_revision: 1,
    }));
  });

  it("explains the empty state", () => {
    mocks.sessions.splice(0);
    render(<SessionDeck agentId="companion_x" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sessions" }));
    expect(screen.queryByText("No saved sessions yet. Start a chat to create one.")).not.toBeNull();
  });
});
