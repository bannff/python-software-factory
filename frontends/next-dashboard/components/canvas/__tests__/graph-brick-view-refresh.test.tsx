import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useEffect } from "react";

const mounted = vi.fn();
vi.mock("../graph-detail-panel", () => ({
  GraphDetailPanel: () => { useEffect(() => { mounted(); }, []); return <p>graph</p>; },
}));
vi.mock("../brick-view-renderer", () => ({ default: () => null }));

import GraphBrickView from "../graph-brick-view";
import { Refreshable } from "../refreshable";
import { useMutationRefresh } from "../refresh-context";

function Mutator() {
  const { notify } = useMutationRefresh();
  return <button type="button" onClick={notify}>mutate</button>;
}

describe("GraphBrickView", () => {
  it("refetches its summary view after a successful mutation", () => {
    render(<Refreshable label="chain"><Mutator /><GraphBrickView viewTool="blockchain_get_views" /></Refreshable>);
    expect(mounted).toHaveBeenCalledTimes(1);
    act(() => { fireEvent.click(screen.getByText("mutate")); });
    expect(mounted).toHaveBeenCalledTimes(2);
  });
});
