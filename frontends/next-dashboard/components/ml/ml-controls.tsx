"use client";

import { useWorkbenchContext } from "@/lib/workbench-context";
import { BaseModelsPanel } from "./base-models-panel";
import { DatasetsPanel } from "./datasets-panel";
import { FineTunePanel } from "./finetune-panel";
import { TrainPanel } from "./train-panel";

/** The ML view's own brick id; the first sub-tab (Overview) is the default when none is selected. */
const ML_BRICK = "machine_learning";
const ASSETS_ON = new Set(["ml-overview", "ml-models"]);
const TRAINING_ON = new Set(["ml-experiments", "ml-models"]);

/** Assets (base models, datasets, jobs) on Overview and Models; the training form on Experiments and Models. */
export function MlControls() {
  const selected = useWorkbenchContext().selectedBrickViews[ML_BRICK] ?? "ml-overview";
  return (
    <>
      {ASSETS_ON.has(selected) && (
        <>
          <BaseModelsPanel />
          <DatasetsPanel />
          <FineTunePanel />
        </>
      )}
      {TRAINING_ON.has(selected) && <TrainPanel />}
    </>
  );
}
