import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const workbench = { focusRun: vi.fn(), switchView: vi.fn() };
vi.mock("@/lib/workbench-context", () => ({ useWorkbenchContext: () => workbench }));

import { FindingLinks } from "../finding-links";

beforeEach(() => { workbench.focusRun.mockClear(); workbench.switchView.mockClear(); });

describe("FindingLinks", () => {
  it("opens the run in Timeline", () => {
    render(<FindingLinks runId="run-7" />);
    fireEvent.click(screen.getByRole("button", { name: "Open run in Timeline" }));
    expect(workbench.focusRun).toHaveBeenCalledWith("run-7");
    expect(workbench.switchView).toHaveBeenCalledWith("timeline-v2");
  });

  it("opens the run in Graph", () => {
    render(<FindingLinks runId="run-7" />);
    fireEvent.click(screen.getByRole("button", { name: "Open run in Graph" }));
    expect(workbench.focusRun).toHaveBeenCalledWith("run-7");
    expect(workbench.switchView).toHaveBeenCalledWith("graph");
  });

  it("renders nothing for a finding with no run", () => {
    const { container } = render(<FindingLinks />);
    expect(container.firstChild).toBeNull();
  });
});
