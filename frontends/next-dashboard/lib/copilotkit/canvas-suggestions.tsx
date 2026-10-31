"use client";

/**
 * <CanvasSuggestions /> — wires CopilotKit v2's `useConfigureSuggestions`
 * to the Companion-X workbench so chat starter chips track the active
 * canvas view (bd-4y5d).
 *
 * Mounted next to <FrontendTools /> inside <CopilotProvider>, AFTER
 * <WorkbenchProvider> so `useWorkbenchContext()` resolves. Suggestions
 * are scoped to `consumerAgentId: "companion_x"` to match the agent id
 * passed to <CopilotChat>.
 *
 * Available `before-first-message` only — once the user types, the chip
 * row collapses and the agent takes over.
 *
 * The "settings" view intentionally has no chips: the screen is
 * configuration-only, so nudging the user to ask the agent about it
 * adds noise.
 */

import { useConfigureSuggestions } from "@copilotkit/react-core/v2";
import { useWorkbenchContext } from "@/lib/workbench-context";
import type { CanvasViewId } from "@/lib/types";

type Chip = { title: string; message: string };

const SEEDS: Record<CanvasViewId, ReadonlyArray<Chip>> = {
  welcome: [
    { title: "What can you do?", message: "What can you do?" },
    { title: "Show me the graph", message: "Show me the graph" },
    { title: "List recent findings", message: "List recent findings" },
  ],
  graph: [
    { title: "Find IDOR endpoints", message: "Find IDOR endpoints in the graph" },
    { title: "Group nodes by type", message: "Group nodes by type" },
    { title: "Highest-priority finding", message: "What's the highest-priority finding?" },
  ],
  findings: [
    { title: "Group by CWE", message: "Group findings by CWE" },
    { title: "Critical findings", message: "Show critical findings" },
    { title: "Generate a report", message: "Generate a report from current findings" },
  ],
  evals: [
    { title: "Show last run", message: "Show me the last evals run" },
    { title: "Compare baseline", message: "Compare against baseline" },
  ],
  "timeline-v2": [
    { title: "What just happened?", message: "What just happened on the timeline?" },
    { title: "Errors only", message: "Show errors only on the timeline" },
  ],
  metrics: [
    { title: "Regression detection", message: "Plot regression detection rate" },
    { title: "Drift alerts", message: "Show drift alerts" },
  ],
  ml: [
    { title: "Recent fine-tuning", message: "List recent fine-tuning jobs" },
    { title: "Dataset stats", message: "Show dataset stats" },
  ],
  games: [
    { title: "Open a CTF", message: "Open a CTF challenge" },
    { title: "RL convergence", message: "Show RL convergence" },
  ],
  blockchain: [
    { title: "Recent transfers", message: "Show recent transfers" },
    { title: "List bounties", message: "List active bounties" },
  ],
  sandbox: [
    { title: "Fresh container", message: "Provision a fresh container" },
    { title: "Active sandboxes", message: "List active sandboxes" },
  ],
  capabilities: [
    { title: "List my crews", message: "List my crews" },
    { title: "What runs next?", message: "Show what is scheduled to run next" },
  ],
  sessions: [
    { title: "Resume recent", message: "Resume my most recent session" },
    { title: "Show archived", message: "Show my archived sessions" },
  ],
  schedules: [
    { title: "What runs next?", message: "Show what is scheduled to run next" },
    { title: "Create a schedule", message: "Help me schedule a task" },
  ],
  lessons: [
    { title: "Review suggestions", message: "Show my suggested lessons" },
    { title: "What have you learned?", message: "Summarize what you have learned from me" },
  ],
  artifacts: [
    { title: "List my artifacts", message: "List my saved artifacts" },
    { title: "Save this work", message: "Save our current result as an artifact" },
    { title: "Review comments", message: "Show open artifact comments" },
  ],
  crews: [
    { title: "List my crews", message: "List my crews" },
    { title: "Create a crew", message: "Create a new crew" },
    { title: "Set the default", message: "Set my default crew" },
  ],
  live: [
    { title: "What's painted?", message: "Describe the canvas you've painted" },
    { title: "Clear the canvas", message: "Clear the live canvas" },
  ],
  settings: [],
};

export function CanvasSuggestions() {
  const { activeView } = useWorkbenchContext();
  const chips = SEEDS[activeView] ?? [];

  // Re-keying on activeView (via deps) ensures CopilotKit clears the
  // stale config when the user flips views.
  useConfigureSuggestions(
    chips.length === 0
      ? null
      : {
          available: "before-first-message",
          consumerAgentId: "companion_x",
          suggestions: chips.map((c) => ({ title: c.title, message: c.message })),
        },
    [activeView],
  );

  return null;
}
