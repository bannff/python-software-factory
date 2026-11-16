import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ComponentTree } from "../renderers/component-renderer";

vi.mock("../renderers/use-tool-data", () => ({
  useToolData: () => ({ data: null, loading: false, error: null }),
}));

function chart(props: Record<string, unknown>) {
  return [{ id: "c", component: "Chart", originalType: "Chart", props }];
}

describe("ChartRenderer bars", () => {
  it("sizes each bar against a track that has a height, so the percentage resolves", () => {
    render(<ComponentTree nodes={chart({ data: [{ name: "a", value: 0.5 }, { name: "b", value: 1 }], xKey: "name", yKey: "value" })} />);
    const bars = screen.getAllByTestId("chart-bar");
    expect(bars).toHaveLength(2);
    for (const bar of bars) {
      const track = bar.parentElement as HTMLElement;
      expect(track.className).toContain("flex-1");
      expect((track.parentElement as HTMLElement).className).toContain("h-full");
    }
    expect((bars[0] as HTMLElement).style.height).toBe("50%");
    expect((bars[1] as HTMLElement).style.height).toBe("100%");
  });

  it("still renders a single point as a visible bar with its label", () => {
    render(<ComponentTree nodes={chart({ data: [{ name: "run-1", value: 0.981 }], xKey: "name", yKey: "value" })} />);
    expect(screen.getByTestId("chart-bar")).toBeTruthy();
    expect(screen.getByText("run-1")).toBeTruthy();
    expect(screen.getByText("0.981")).toBeTruthy();
  });
});
