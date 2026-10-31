import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EmptyGraph } from "../graph-empty-state";

describe("Graph empty topology", () => {
  it("renders the exact focused-run empty message", () => {
    render(<EmptyGraph loading={false} hasLoaded focusedRunId="run-full" onReload={vi.fn()} />);
    expect(screen.getByText("No attributable topology for this workflow run.")).toBeTruthy();
    expect(screen.getByText("Run run-full has no projected nodes or relationships.")).toBeTruthy();
  });
});
