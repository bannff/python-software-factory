import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/api", () => ({ callTool: vi.fn() }));

import { SessionDetail } from "../session-detail";
import type { SessionSummary } from "@/lib/hooks/use-session-list";
import type { Crew } from "@/components/crews/crew-types";

const crew = (id: string, name: string): Crew => ({
  id, name, description: "", persona_id: "p", project: "/w", workspace: "", memory_scope: "m", model: "", triggers: [], revision: 1,
});

function detail(crew_id: string, crews?: readonly Crew[]) {
  const session: SessionSummary = {
    session_id: "s1", thread_id: "t1", title: "T", agent_id: "a", model: "m",
    updated_at: "2026-09-17T12:00:00Z", archived_at: null, revision: 1, crew_id,
    memory_scope: "", pinned_rank: null, unread: false, tags: [], pinned_message_ids: [], summary: "", folder: "",
  };
  render(<SessionDetail session={session} crews={crews} active={false} focusHeading={false} onChanged={vi.fn()} />);
}

describe("SessionDetail crew field", () => {
  it("links to the crew when it exists", () => {
    detail("blue-crew", [crew("blue-crew", "Blue Team")]);
    const link = screen.getByRole("link", { name: "Blue Team" });
    expect(link.getAttribute("href")).toBe("/crews/blue-crew");
  });

  it("marks the crew as removed when the roster no longer has it", () => {
    detail("ghost-crew", [crew("blue-crew", "Blue Team")]);
    expect(screen.queryByRole("link", { name: /ghost-crew/ })).toBeNull();
    expect(screen.getByText(/Crew removed/i)).toBeTruthy();
    expect(screen.getByText(/ghost-crew/)).toBeTruthy();
  });

  it("shows the plain id, without claiming removal, while the roster is unknown", () => {
    detail("blue-crew", undefined);
    expect(screen.getByText("blue-crew")).toBeTruthy();
    expect(screen.queryByText(/removed/i)).toBeNull();
  });

  it("shows a dash for sessions with no crew", () => {
    detail("", [crew("blue-crew", "Blue Team")]);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByText(/removed/i)).toBeNull();
  });
});
