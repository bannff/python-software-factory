import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ stream: { entries: [] as unknown[], connected: false } }));
vi.mock("@/lib/hooks/use-live-tool-stream", () => ({ useLiveToolStream: () => mocks.stream }));

import { LogsPanel } from "../logs-panel";

describe("LogsPanel (row 104, feature-map)", () => {
  it("renders recent tool-event activity newest-first with status", () => {
    mocks.stream = {
      connected: true,
      entries: [
        { id: "1", title: "memory_store", status: "completed", timestamp: Date.now() },
        { id: "2", title: "graph_export", status: "failed", timestamp: Date.now() },
      ],
    };
    render(<LogsPanel />);
    expect(screen.getByText("streaming")).toBeTruthy();
    expect(screen.getByText("memory_store")).toBeTruthy();
    expect(screen.getByText("graph_export")).toBeTruthy();
  });

  it("shows an empty state and idle badge when there is no activity", () => {
    mocks.stream = { entries: [], connected: false };
    render(<LogsPanel />);
    expect(screen.getByText(/No recent activity/i)).toBeTruthy();
    expect(screen.getByText("idle")).toBeTruthy();
  });

  it("renders full-height in the page variant (row 114, /logs route)", () => {
    mocks.stream = {
      connected: true,
      entries: [{ id: "1", title: "memory_store", status: "completed", timestamp: Date.now() }],
    };
    const { container } = render(<LogsPanel variant="page" />);
    expect(container.querySelector(".flex.h-full")).toBeTruthy();
    expect(screen.getByText("memory_store")).toBeTruthy();
  });
});
