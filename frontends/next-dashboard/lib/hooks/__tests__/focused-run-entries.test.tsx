import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { TimelineEntry } from "@/lib/types";

const history = vi.fn();
const live = vi.fn();
vi.mock("@/lib/hooks/use-timeline-data", () => ({ useTimelineData: (...args: unknown[]) => history(...args) }));
vi.mock("@/lib/hooks/use-live-tool-stream", () => ({ useLiveToolStream: () => live() }));

import { useFocusedRunEntries } from "@/lib/hooks/use-focused-run-entries";

function row(id: string, run?: string): TimelineEntry { return { id, type: "tool_call", title: id, status: "completed", timestamp: 1, workflow_run_id: run }; }

describe("focused Timeline attribution", () => {
  it("uses the exact API and excludes other-run and unattributed retained rows", () => {
    history.mockReturnValue({ entries: [row("h-exact", "run-a"), row("h-other", "run-b"), row("h-none")], loading: false, error: null, available: true });
    live.mockReturnValue({ entries: [row("l-exact", "run-a"), row("l-other", "run-b"), row("l-none")], connected: true });
    const { result } = renderHook(() => useFocusedRunEntries("run-a"));
    expect(history).toHaveBeenCalledWith("run-a", true);
    expect(result.current.entries.map((entry) => entry.id)).toEqual(["l-exact", "h-exact"]);
  });

  it("preserves exact API unavailability instead of falling back", () => {
    history.mockReturnValue({ entries: [], loading: false, error: "backend down", available: false });
    live.mockReturnValue({ entries: [row("global", "run-b")], connected: true });
    const { result } = renderHook(() => useFocusedRunEntries("run-a"));
    expect(result.current).toMatchObject({ entries: [], error: "backend down", available: false });
  });
});
