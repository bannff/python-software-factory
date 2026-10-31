import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RunsSelector } from "../runs-selector";


describe("workflow run selector focus", () => {
  it("shows registered and dynamic durable runs without auto-focusing either", async () => {
    const registered = "wfr:v1:registered:001";
    const dynamic = "wfr:v1:dynamic:002";
    const listRecentRuns = vi.fn(async () => [
      { run_id: registered, status: "running", started_at: "2026-08-21T10:00:00Z" },
      { run_id: dynamic, status: "succeeded", started_at: "2026-08-21T10:01:00Z" },
    ]);
    const focusRun = vi.fn();

    render(
      <RunsSelector
        listRecentRuns={listRecentRuns}
        focusedRunId={null}
        onFocusRun={focusRun}
        onClear={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Select a workflow run" }));
    await waitFor(() => expect(listRecentRuns).toHaveBeenCalledWith(20));
    expect(await screen.findByTitle(registered)).toBeTruthy();
    expect(screen.getByTitle(dynamic)).toBeTruthy();
    expect(focusRun).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTitle(dynamic));
    expect(focusRun).toHaveBeenCalledOnce();
    expect(focusRun).toHaveBeenCalledWith(dynamic);
  });
});
