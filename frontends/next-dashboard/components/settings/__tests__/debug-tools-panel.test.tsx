import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ stream: { entries: [] as unknown[], connected: false } }));
vi.mock("@/lib/hooks/use-live-tool-stream", () => ({ useLiveToolStream: () => mocks.stream }));

import { DebugToolsPanel } from "../debug-tools-panel";

describe("DebugToolsPanel (row 112, feature-map)", () => {
  it("shows connected stream state and the recent event count", () => {
    mocks.stream = { entries: [{ id: "1" }, { id: "2" }], connected: true };
    render(<DebugToolsPanel />);
    expect(screen.getByText("connected")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("Dashboard origin")).toBeTruthy();
  });

  it("shows a disconnected stream state", () => {
    mocks.stream = { entries: [], connected: false };
    render(<DebugToolsPanel />);
    expect(screen.getByText("disconnected")).toBeTruthy();
  });
});
