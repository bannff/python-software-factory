"use client";

import { useWorkbenchContext } from "@/lib/workbench-context";
import { BaseModelsPanel } from "./base-models-panel";
import { DatasetsPanel } from "./datasets-panel";
import { FineTunePanel } from "./finetune-panel";
import { TrainPanel } from "./train-panel";

/** The ML view's own brick id; Overview (the default) stays state-only. */
const ML_BRICK = "machine_learning";

/** Assets (base models, datasets, jobs) live on Models; the training form on Experiments. */
export function MlControls() {
  const selected = useWorkbenchContext().selectedBrickViews[ML_BRICK] ?? "ml-overview";
  if (selected === "ml-models") return (
    <>
      <BaseModelsPanel />
      <DatasetsPanel />
      <FineTunePanel />
    </>
  );
  return selected === "ml-experiments" ? <TrainPanel /> : null;
}
