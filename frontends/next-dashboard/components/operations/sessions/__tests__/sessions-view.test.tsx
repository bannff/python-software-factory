import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  list: {
    sessions: [] as unknown[],
    loading: false,
    error: null as string | null,
    refresh: vi.fn(),
  },
  includeArchived: false,
  callTool: vi.fn(),
}));

function session(over: Record<string, unknown> = {}) {
  return {
    session_id: "sess-abc123", thread_id: "thread-1", title: "Threat model review",
    agent_id: "red-team", model: "openrouter/x/y", updated_at: new Date().toISOString(),
    archived_at: null, revision: 2, crew_id: "", memory_scope: "", pinned_rank: null,
    unread: false, tags: [], ...over,
  };
}

vi.mock("@/lib/hooks/use-session-list", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/hooks/use-session-list")>();
  return {
    ...actual,
    useSessionList: (includeArchived: boolean) => {
      mocks.includeArchived = includeArchived;
      return mocks.list;
    },
  };
});
vi.mock("@/lib/hooks/use-personas", () => ({
  usePersonas: () => ({ personas: [{ id: "red-team", name: "Red Team" }], loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => mocks.callTool(...args) }));

import SessionsView from "../sessions-view";

function openSession(title = "Threat model review") {
  fireEvent.click(screen.getByRole("button", { name: new RegExp(`Open session ${title}`) }));
}

beforeEach(() => {
  mocks.list.sessions = [session()];
  mocks.list.loading = false;
  mocks.list.error = null;
  mocks.list.refresh.mockReset();
  mocks.includeArchived = false;
  mocks.callTool.mockReset().mockResolvedValue({ tool: "x", result: { session: session({ title: "Renamed", revision: 3 }) } });
});

describe("SessionsView states and accessibility", () => {
  it("uses the session title as the primary label, resolved persona name, never the raw id", () => {
    render(<SessionsView />);
    expect(screen.getByRole("heading", { name: "Sessions" })).toBeTruthy();
    expect(screen.getAllByText("Threat model review").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Red Team/).length).toBeGreaterThan(0);
    expect(screen.queryByText("sess-abc123")).toBeNull();
  });
  it("keeps bare /sessions neutral until the user selects a row", () => {
    render(<SessionsView />);
    expect(screen.queryByRole("button", { name: "Rename" })).toBeNull();
    expect(screen.getByText("Select a session to see its details.")).toBeTruthy();
    openSession();
    expect(screen.getByRole("button", { name: "Rename" })).toBeTruthy();
  });
  it("groups pinned and unpinned sessions by recency", () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const older = new Date();
    older.setDate(older.getDate() - 10);
    mocks.list.sessions = [
      session({ pinned_rank: 1024 }),
      session({ session_id: "s-yesterday", title: "Yesterday row", updated_at: yesterday.toISOString() }),
      session({ session_id: "s-older", title: "Older row", updated_at: older.toISOString() }),
    ];
    render(<SessionsView />);
    expect(screen.getByRole("heading", { name: "Pinned" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Yesterday" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Older" })).toBeTruthy();
  });
  it("filters to sessions with pending completion delivery", () => {
    mocks.list.sessions = [
      session({ unread: true, title: "Needs attention" }),
      session({ session_id: "s-read", title: "Already read" }),
    ];
    render(<SessionsView />);
    fireEvent.click(screen.getByRole("button", { name: /unread/i }));
    expect(screen.getByText("Needs attention")).toBeTruthy();
    expect(screen.queryByText("Already read")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^all$/i }));
    expect(screen.getByText("Already read")).toBeTruthy();
  });
  it("filters by authoritative Session tags", () => {
    mocks.list.sessions = [
      session({ tags: ["urgent"], title: "Urgent row" }),
      session({ session_id: "s-other", title: "Other row" }),
    ];
    render(<SessionsView />);
    fireEvent.click(screen.getByRole("button", { name: "#urgent" }));
    expect(screen.getByText("Urgent row")).toBeTruthy();
    expect(screen.queryByText("Other row")).toBeNull();
  });
  it("filters by session folder (row 6, feature-map)", () => {
    mocks.list.sessions = [
      session({ folder: "Client work", title: "Filed row" }),
      session({ session_id: "s-unfiled", title: "Unfiled row" }),
    ];
    render(<SessionsView />);
    expect(screen.getByLabelText("Folder Client work")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "📁 Client work" }));
    expect(screen.getByText("Filed row")).toBeTruthy();
    expect(screen.queryByText("Unfiled row")).toBeNull();
  });
  it("shows a truthful empty state when there are no sessions", () => {
    mocks.list.sessions = [];
    render(<SessionsView />);
    expect(screen.getByText(/No active sessions/i)).toBeTruthy();
  });
  it("shows a loading state before any rows arrive", () => {
    mocks.list.sessions = [];
    mocks.list.loading = true;
    render(<SessionsView />);
    expect(screen.getByText(/Loading sessions/i)).toBeTruthy();
  });
  it("renders an error with a retry that refreshes", () => {
    mocks.list.sessions = [];
    mocks.list.error = "Sessions unavailable";
    render(<SessionsView />);
    expect(screen.getByRole("alert").textContent).toContain("Sessions unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mocks.list.refresh).toHaveBeenCalled();
  });
  it("toggles the archived filter through to the shared list hook", async () => {
    render(<SessionsView />);
    fireEvent.click(screen.getByRole("button", { name: "Show archived sessions" }));
    expect(mocks.includeArchived).toBe(true);
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_count_archived", {}));
  });
  it("marks an archived session and offers reopen instead of archive", () => {
    mocks.list.sessions = [session({ archived_at: new Date().toISOString() })];
    render(<SessionsView />);
    expect(screen.getByLabelText(/\(archived\)/)).toBeTruthy();
    openSession();
    expect(screen.getByRole("button", { name: "Reopen" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
  });
});

describe("SessionsView actions and focus", () => {
  it("delegates resume and create to the runtime owner (no duplicated state)", async () => {
    const onResumeSession = vi.fn();
    const onCreateSession = vi.fn();
    render(<SessionsView onResumeSession={onResumeSession} onCreateSession={onCreateSession} />);
    fireEvent.click(screen.getByRole("button", { name: "New session" }));
    await waitFor(() => expect(onCreateSession).toHaveBeenCalled());
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(onResumeSession).toHaveBeenCalledWith(
      expect.objectContaining({ session_id: "sess-abc123" }),
    ));
  });
  it("pins through the revision-fenced Session tool", async () => {
    mocks.list.sessions = [session({ pinned_rank: 1024 })];
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Unpin session" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_set_pinned", {
      session_id: "sess-abc123", pinned: false, expected_revision: 2,
    }));
  });
  it("manually moves a pinned session through the revision-fenced tool", async () => {
    mocks.list.sessions = [
      session({ pinned_rank: 1024 }),
      session({ session_id: "sess-two", thread_id: "thread-2", title: "Second", pinned_rank: 2048 }),
    ];
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Move pinned session down" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_move_pinned", {
      session_id: "sess-abc123", before_session_id: null, expected_revision: 2,
    }));
  });
  it("renames through the real MCP tool with the CAS revision", async () => {
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    fireEvent.change(screen.getByLabelText("Session name"), { target: { value: "Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_rename", {
      session_id: "sess-abc123", title: "Renamed", expected_revision: 2,
    }));
  });
  it("focuses the detail heading for a deep-link target then reports it handled", async () => {
    const onFocusHandled = vi.fn();
    render(<SessionsView focusSessionId="sess-abc123" onFocusHandled={onFocusHandled} />);
    const heading = await screen.findByRole("heading", { name: "Threat model review" });
    await waitFor(() => expect(document.activeElement).toBe(heading));
    expect(onFocusHandled).toHaveBeenCalled();
  });
  it("requires a confirm click before deleting, then calls the real MCP tool with the CAS revision", async () => {
    mocks.callTool.mockReset().mockResolvedValue({
      tool: "session_delete", result: { ok: true, data: { session_id: "sess-abc123", deleted: true } },
    });
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Delete session" }));
    expect(mocks.callTool).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_delete", {
      session_id: "sess-abc123", expected_revision: 2,
    }));
  });
  it("cancels the delete confirmation without calling any tool", () => {
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Delete session" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByText("Delete permanently?")).toBeNull();
    expect(mocks.callTool).not.toHaveBeenCalled();
  });
  it("clears the selection and refreshes after a successful delete", async () => {
    mocks.callTool.mockReset().mockResolvedValue({
      tool: "session_delete", result: { ok: true, data: { session_id: "sess-abc123", deleted: true } },
    });
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Delete session" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    await waitFor(() => expect(screen.getByText("Select a session to see its details.")).toBeTruthy());
    expect(mocks.list.refresh).toHaveBeenCalled();
  });
  it("forks a session with one click, no confirmation needed (row 14, feature-map)", async () => {
    mocks.callTool.mockReset().mockResolvedValue({
      tool: "session_fork",
      result: { session: session({ session_id: "sess-forked", title: "Threat model review (fork)", revision: 1 }) },
    });
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Fork session" }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_fork", {
      session_id: "sess-abc123",
    }));
    await waitFor(() => expect(mocks.callTool).toHaveBeenCalledWith("session_fork_transcript", {
      source_session_id: "sess-abc123", target_session_id: "sess-forked",
    }));
  });
  it("selects the newly forked session once the list refresh includes it", async () => {
    mocks.callTool.mockReset().mockResolvedValue({
      tool: "session_fork",
      result: { session: session({ session_id: "sess-forked", title: "Threat model review (fork)", revision: 1 }) },
    });
    mocks.list.refresh.mockImplementation(() => {
      mocks.list.sessions = [...mocks.list.sessions, session({
        session_id: "sess-forked", title: "Threat model review (fork)", revision: 1,
      })];
    });
    const { rerender } = render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Fork session" }));
    await waitFor(() => expect(mocks.list.refresh).toHaveBeenCalled());
    rerender(<SessionsView />);
    expect(screen.getByRole("heading", { name: "Threat model review (fork)" })).toBeTruthy();
  });
  it("shows a safe error and keeps the source session selected if the fork fails", async () => {
    mocks.callTool.mockReset().mockRejectedValue(new Error("API 500: internal owner=abc"));
    render(<SessionsView />);
    openSession();
    fireEvent.click(screen.getByRole("button", { name: "Fork session" }));
    await waitFor(() => expect(screen.getByText(/Couldn.t fork this session/)).toBeTruthy());
    expect(screen.getByRole("heading", { name: "Threat model review" })).toBeTruthy();
  });
});
