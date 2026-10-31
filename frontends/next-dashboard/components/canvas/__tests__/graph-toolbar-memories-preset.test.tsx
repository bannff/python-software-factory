import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { GraphToolbar } from "../graph-toolbar";

const BASE_PROPS = {
  query: "", searchMode: "type" as const, activePreset: null, loading: false,
  broadControlsDisabled: false, runsSelector: <div />,
  activity: { runs: false, agents: false, invocations: false },
  onQueryChange: vi.fn(), onToggleSearchMode: vi.fn(), onSearch: vi.fn(),
  onLoadPreset: vi.fn(), onFit: vi.fn(), onReset: vi.fn(),
  stats: null, visibleNodes: 0, visibleLinks: 0,
};

describe("GraphToolbar Memories preset (row 51)", () => {
  it("calls onLoadPreset with the lowercase memory entity type", () => {
    const onLoadPreset = vi.fn();
    render(<GraphToolbar {...BASE_PROPS} onLoadPreset={onLoadPreset} />);
    fireEvent.click(screen.getByRole("button", { name: "Memories" }));
    expect(onLoadPreset).toHaveBeenCalledWith("memory");
  });
});
