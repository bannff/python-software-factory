"use client";

import { useWorkbenchContext } from "@/lib/workbench-context";
import { BaseModelsPanel } from "./base-models-panel";
import { DatasetsPanel } from "./datasets-panel";
import { FineTunePanel } from "./finetune-panel";

/** The ML view's own brick id and the sub-tabs these controls belong to (the first sub-tab is the default). */
const ML_BRICK = "machine_learning";
const SHOWN_ON = new Set(["ml-overview", "ml-models"]);

/** Base models, datasets and fine-tuning jobs, only where they make sense: Overview and Models. */
export function MlControls() {
  const selected = useWorkbenchContext().selectedBrickViews[ML_BRICK];
  if (selected !== undefined && !SHOWN_ON.has(selected)) return null;
  return (
    <>
      <BaseModelsPanel />
      <DatasetsPanel />
      <FineTunePanel />
    </>
  );
}
