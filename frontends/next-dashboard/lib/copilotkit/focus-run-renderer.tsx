"use client";

import { useRenderTool } from "@copilotkit/react-core/v2";
import { Focus } from "lucide-react";
import { z } from "zod";
import { ToolCallCard } from "./tool-call-card";

const FocusRunArgs = z.object({ run_id: z.string() });

export function useFocusRunRenderer() {
  useRenderTool({
    name: "fe_focus_run",
    parameters: FocusRunArgs,
    render: ({ status, parameters }) => {
      const runId = parameters?.run_id || "workflow run";
      return (
        <ToolCallCard
          name="fe_focus_run"
          title="Focus workflow run"
          icon={<Focus className="h-3.5 w-3.5" />}
          status={status}
          previewLine={status === "complete" ? `Focused ${runId}` : `Focusing ${runId}…`}
        />
      );
    },
  });
}
