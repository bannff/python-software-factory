"use client";

/**
 * <FrontendTools /> — registers CopilotKit v2 ``useFrontendTool``s
 * that drive the workbench from the chat agent (bd-115z, paired with
 * bd-vw04).
 *
 * Round-trip: backend stub (registered for the turn by
 * ``FrontendToolPlugin``) emits a deferred sentinel and ends the LangChain
 * turn; AG-UI surfaces the tool call. CopilotKit v2 runs THIS handler, gets
 * a result, then re-POSTs ``/ag-ui/run`` with the full message history
 * including the ``role=tool`` reply. LangChain resumes from there.
 *
 * Tool names MUST match the ``fe_`` prefix used by the backend
 * ``_StubAgentTool`` so registry registration keys line up.
 */
import { z } from "zod";
import { useFrontendTool, useHumanInTheLoop } from "@copilotkit/react-core/v2";
import { toast } from "sonner";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { syncCanvasRoute } from "@/lib/canvas-routes";
import type { CanvasViewId } from "@/lib/types";
import { ShellApprovalCard } from "./shell-approval-card";
import { useFocusRunRenderer } from "./focus-run-renderer";
import { useArtifactNavigationTool } from "./artifact-navigation-tool";
import { OperationsNavigationTools } from "./operations-navigation-tools";

const VIEW_IDS = [
  "welcome",
  "graph",
  "timeline-v2",
  "findings",
  "evals",
  "metrics",
  "ml",
  "games",
  "blockchain",
  "sandbox",
  "capabilities",
  "sessions",
  "schedules",
  "lessons",
  "artifacts",
  "crews",
  "live",
  "settings",
] as const satisfies ReadonlyArray<CanvasViewId>;

const VIEW_LABELS: Record<CanvasViewId, string> = {
  welcome: "Welcome",
  graph: "Graph",
  "timeline-v2": "Timeline",
  findings: "Findings",
  evals: "Evals",
  metrics: "Metrics",
  ml: "ML",
  games: "Games",
  blockchain: "Blockchain",
  sandbox: "Sandbox",
  capabilities: "Agent Capabilities",
  sessions: "Sessions",
  schedules: "Schedules",
  lessons: "Lessons",
  artifacts: "Artifacts",
  crews: "Crews",
  live: "Live",
  settings: "Settings",
};

const NavigateArgs = z.object({
  view: z.enum(VIEW_IDS).describe("The canvas view id to switch to."),
});

const FocusRunArgs = z.object({
  run_id: z.string().trim().min(1).describe("The full workflow run ID to focus."),
});

const BrickViewArgs = z.object({
  brick: z.string().describe("The brick id that owns the fetched views."),
  view_id: z.string().describe("A registered view id for that brick."),
});

const ShellApproveArgs = z.object({
  tool: z.string().describe("The tool name to approve (e.g. 'shell' or 'python_repl')."),
  command: z.string().describe("The exact command the agent wants to run."),
});

export function FrontendTools() {
  const workbench = useWorkbenchContext();
  useFocusRunRenderer();
  useArtifactNavigationTool();

  useFrontendTool({
    name: "fe_navigate_canvas",
    description:
      "Switch the Companion-X canvas to a different view. Use this when " +
      "the user asks to open or focus a panel, e.g. 'show me findings' " +
      "or 'open the graph'.",
    parameters: NavigateArgs,
    handler: async ({ view }) => {
      // bd:python-factory-3hkqx — CopilotKit-core's executeSpecificTool
      // does NOT enforce the Zod schema. Without this guard, an agent
      // that picks an invalid view id would slip through to switchView and
      // produce a blank-label tab.
      if (!(VIEW_IDS as readonly string[]).includes(view)) {
        return {
          success: false,
          error:
            `Unknown view ${JSON.stringify(view)}; valid: ${VIEW_IDS.join(", ")}`,
        };
      }
      const previous = workbench.activeView;
      syncCanvasRoute(view);
      workbench.switchView(view);
      if (previous !== view) {
        const label = VIEW_LABELS[view];
        toast.info(`Switched to ${label} view`, {
          duration: 2200,
          position: "top-center",
          style: {
            borderColor: "rgb(139 92 246 / 0.5)",
            background: "rgb(139 92 246 / 0.08)",
            color: "var(--foreground)",
          },
        });
      }
      return { success: true, view };
    },
  });

  useFrontendTool({
    name: "fe_focus_run",
    description:
      "Focus every run-aware canvas on one exact workflow run ID. This only " +
      "updates shared focus; use fe_navigate_canvas separately to change views.",
    parameters: FocusRunArgs,
    handler: async ({ run_id }) => {
      // CopilotKit 1.53.0 executeSpecificTool JSON-parses arguments but does
      // not enforce the registered Zod schema before invoking this handler.
      const parsed = FocusRunArgs.safeParse({ run_id });
      if (!parsed.success) {
        return { success: false, error: "run_id must be a non-empty full workflow run ID" };
      }
      workbench.focusRun(parsed.data.run_id);
      return { success: true, run_id: parsed.data.run_id };
    },
  });

  useFrontendTool({
    name: "fe_select_brick_view",
    description:
      "Select a fetched brick-declared subview by brick and view id. " +
      "Only ids registered by the brick renderer are accepted.",
    parameters: BrickViewArgs,
    handler: async ({ brick, view_id }) => {
      const valid = workbench.brickViews[brick] ?? [];
      if (!valid.some((view) => view.id === view_id)) {
        return {
          success: false,
          error: `Unknown view ${JSON.stringify(view_id)} for ${JSON.stringify(brick)}`,
          valid_view_ids: valid.map((view) => view.id),
        };
      }
      workbench.selectBrickView(brick, view_id);
      return { success: true, brick, view_id };
    },
  });

  // HITL shell/python_repl approval (bd:python-factory-wog0b).
  // useHumanInTheLoop is the framework-native pattern: it wraps
  // useFrontendTool with an SDK-supplied promise bridge — the render
  // fn gets a live `respond` during status==="executing", and calling
  // respond() resolves the tool-call so the LangChain agent resumes with
  // the decision in message history. ShellApprovalPlugin (backend) is
  // the enforcement layer that cancels shell until this approval lands.
  // The card MUST echo back the exact (truncated) command via respond so
  // the plugin's history-scan matches (cmd is truncated to 300 chars
  // backend-side in _cmd_from_input).
  useHumanInTheLoop({
    name: "fe_approve_shell",
    description:
      "Ask the user to approve or deny a shell/python_repl command before " +
      "the agent executes it. MUST be called before any shell or " +
      "python_repl invocation. The user's decision is returned as the result.",
    parameters: ShellApproveArgs,
    render: ({ args, status, respond }) => (
      <ShellApprovalCard
        tool={args?.tool ?? "shell"}
        command={args?.command ?? ""}
        status={status}
        onDecision={(approved) =>
          respond?.({ approved, tool: args?.tool ?? "shell", command: args?.command ?? "" })
        }
      />
    ),
  });

  return <OperationsNavigationTools />;
}
