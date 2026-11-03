import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const workbench = { selectedBrickViews: {} as Record<string, string> };
vi.mock("@/lib/workbench-context", () => ({ useWorkbenchContext: () => workbench }));
vi.mock("../base-models-panel", () => ({ BaseModelsPanel: () => <p>base models panel</p> }));
vi.mock("../datasets-panel", () => ({ DatasetsPanel: () => <p>datasets panel</p> }));
vi.mock("../finetune-panel", () => ({ FineTunePanel: () => <p>fine-tuning panel</p> }));

import { MlControls } from "../ml-controls";

beforeEach(() => { workbench.selectedBrickViews = {}; });

describe("MlControls", () => {
  it("shows all three panels on the default (Overview) sub-tab", () => {
    render(<MlControls />);
    expect(screen.getByText("base models panel")).toBeTruthy();
    expect(screen.getByText("datasets panel")).toBeTruthy();
    expect(screen.getByText("fine-tuning panel")).toBeTruthy();
  });

  it("shows them on the Models sub-tab", () => {
    workbench.selectedBrickViews = { machine_learning: "ml-models" };
    render(<MlControls />);
    expect(screen.getByText("fine-tuning panel")).toBeTruthy();
  });

  it.each(["ml-experiments", "ml-learning-runs", "ml-lineage"])("hides them on %s", (id) => {
    workbench.selectedBrickViews = { machine_learning: id };
    const { container } = render(<MlControls />);
    expect(container.firstChild).toBeNull();
  });
});
