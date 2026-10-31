import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => callTool(...args) }));

import { SessionDetail } from "../session-detail";
import type { SessionSummary } from "@/lib/hooks/use-session-list";

function session(over: Partial<SessionSummary> = {}): SessionSummary {
  return {
    session_id: "s1", thread_id: "t1", title: "Deploy review", agent_id: "companion-x-default",
    model: "openrouter/x/y", updated_at: "2026-09-17T12:00:00Z", archived_at: null, revision: 4,
    crew_id: "", memory_scope: "", pinned_rank: null, unread: false, tags: [], pinned_message_ids: [], summary: "", folder: "", ...over,
  };
}

const HISTORY = {
  tool: "agent_session_history",
  result: {
    messages: [
      { id: "m1", role: "user", content: "deploy the fix", tool_calls: [], tool_call_id: null },
      { id: "m2", role: "assistant", content: "shipped it", tool_calls: [], tool_call_id: null },
    ],
  },
};

beforeEach(() => callTool.mockReset());

describe("SessionDetail — rolling summary (row 18)", () => {
  it("shows an empty state and a Generate button when there is no summary", () => {
    render(<SessionDetail session={session()} active={false} focusHeading={false} onChanged={vi.fn()} />);
    expect(screen.getByText(/No summary yet/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Generate summary/i })).toBeTruthy();
  });

  it("loads the transcript, generates the summary with the CAS revision, and reports the result", async () => {
    callTool.mockImplementation(async (tool: string) => {
      if (tool === "agent_session_history") return HISTORY;
      if (tool === "session_generate_summary") {
        return { tool, result: { session: session({ summary: "Deploy fix shipped.", revision: 5 }) } };
      }
      return { tool, result: {} };
    });
    const onChanged = vi.fn();
    render(<SessionDetail session={session()} active={false} focusHeading={false} onChanged={onChanged} />);

    fireEvent.click(screen.getByRole("button", { name: /Generate summary/i }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(callTool).toHaveBeenCalledWith("agent_session_history", { session_id: "s1" });
    expect(callTool).toHaveBeenCalledWith("session_generate_summary", {
      session_id: "s1",
      excerpt: "user: deploy the fix\nassistant: shipped it",
      expected_revision: 4,
    });
    expect(onChanged.mock.calls[0][0].summary).toBe("Deploy fix shipped.");
  });

  it("files the session under a folder via session_set_folder with the CAS revision", async () => {
    callTool.mockImplementation(async (tool: string) => {
      if (tool === "session_set_folder") {
        return { tool, result: { session: session({ folder: "Client work", revision: 5 }) } };
      }
      return { tool, result: {} };
    });
    const onChanged = vi.fn();
    render(<SessionDetail session={session()} active={false} focusHeading={false} onChanged={onChanged} />);

    fireEvent.change(screen.getByLabelText("Session folder"), { target: { value: "Client work" } });
    fireEvent.click(screen.getByRole("button", { name: "Save folder" }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    expect(callTool).toHaveBeenCalledWith("session_set_folder", {
      session_id: "s1", folder: "Client work", expected_revision: 4,
    });
    expect(onChanged.mock.calls[0][0].folder).toBe("Client work");
  });

  it("renders an existing summary and offers Regenerate", () => {
    render(<SessionDetail session={session({ summary: "Prior summary here." })} active={false}
      focusHeading={false} onChanged={vi.fn()} />);
    expect(screen.getByText("Prior summary here.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Regenerate summary/i })).toBeTruthy();
  });

  it("does not call generate when the transcript is empty, and says so", async () => {
    callTool.mockImplementation(async (tool: string) => {
      if (tool === "agent_session_history") return { tool, result: { messages: [] } };
      return { tool, result: {} };
    });
    const onChanged = vi.fn();
    render(<SessionDetail session={session()} active={false} focusHeading={false} onChanged={onChanged} />);

    fireEvent.click(screen.getByRole("button", { name: /Generate summary/i }));

    await waitFor(() => expect(screen.getByText(/no conversation to summarize yet/i)).toBeTruthy());
    expect(callTool).not.toHaveBeenCalledWith("session_generate_summary", expect.anything());
    expect(onChanged).not.toHaveBeenCalled();
  });
});
