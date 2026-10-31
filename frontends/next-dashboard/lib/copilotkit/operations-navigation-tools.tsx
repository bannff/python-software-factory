"use client";

import { z } from "zod";
import { useRouter } from "next/navigation";
import { useFrontendTool } from "@copilotkit/react-core/v2";
import { useWorkbenchContext } from "@/lib/workbench-context";
import type { CanvasViewId } from "@/lib/types";

const IdArgs = z.object({ id: z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_.:=+-]{0,255}$/) });
const TARGETS = [
  ["session", "sessions"], ["schedule", "schedules"], ["lesson", "lessons"],
] as const;

function OperationNavigationTool({ kind, view }: {
  kind: "session" | "schedule" | "lesson";
  view: CanvasViewId;
}) {
  const router = useRouter();
  const workbench = useWorkbenchContext();
  useFrontendTool({
    name: `fe_navigate_${kind}`,
    description: `Open one exact ${kind} in the Companion-X ${view} view.`,
    parameters: IdArgs,
    handler: async ({ id }) => {
      const parsed = IdArgs.safeParse({ id });
      if (!parsed.success) return { success: false, error: `A valid ${kind} id is required.` };
      workbench.switchView(view);
      router.push(`/${view}/${encodeURIComponent(parsed.data.id)}`);
      return { success: true, view, id: parsed.data.id };
    },
  });
  return null;
}

/** Mount one stable CopilotKit frontend-tool component per Operations target. */
export function OperationsNavigationTools() {
  return <>{TARGETS.map(([kind, view]) => (
    <OperationNavigationTool key={kind} kind={kind} view={view} />
  ))}</>;
}
