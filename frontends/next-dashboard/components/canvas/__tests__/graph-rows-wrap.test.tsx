import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { GraphToolbar } from "../graph-toolbar";
import { GraphTypeFilters } from "../graph-type-filters";

const TOOLBAR = {
  query: "", searchMode: "type" as const, activePreset: null, loading: false,
  broadControlsDisabled: false, runsSelector: <div />,
  activity: { runs: false, agents: false, invocations: false },
  onQueryChange: vi.fn(), onToggleSearchMode: vi.fn(), onSearch: vi.fn(),
  onLoadPreset: vi.fn(), onFit: vi.fn(), onReset: vi.fn(),
  stats: null, visibleNodes: 0, visibleLinks: 0,
};

// A narrow split pane must wrap these rows instead of hiding controls behind a sideways scrollbar.
describe("Graph rows in a narrow pane", () => {
  it("wraps the toolbar", () => {
    const { container } = render(<GraphToolbar {...TOOLBAR} />);
    const row = container.firstElementChild as HTMLElement;
    expect(row.className).toContain("flex-wrap");
    expect(row.className).not.toContain("overflow-x-auto");
  });

  it("wraps the type chips", () => {
    const { container } = render(
      <GraphTypeFilters typeCounts={[["Agent", 2]]} hiddenTypes={new Set()} visibleCount={2} onToggleType={vi.fn()} />,
    );
    const row = container.firstElementChild as HTMLElement;
    expect(row.className).toContain("flex-wrap");
    expect(row.className).not.toContain("overflow-x-auto");
  });
});
