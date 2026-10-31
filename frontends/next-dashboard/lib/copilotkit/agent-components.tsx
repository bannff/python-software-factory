"use client";

/**
 * <AgentComponents /> — registers CopilotKit v2 `useComponent`
 * components the LLM can summon mid-stream (bd-kzsl Phase 1).
 *
 * Different mental model from `useFrontendTool` / `useRenderTool`:
 *   - useFrontendTool   — agent emits a tool call; we run a handler
 *   - useRenderTool     — agent emits a tool result; we render it
 *   - useComponent      — agent emits a typed component reference and
 *                         CopilotKit renders it inline in the chat
 *
 * Phase 1 ships 3 useful components — register-only. A follow-up bd
 * teaches the agent's prompt when to summon them; until then they
 * live in the CopilotKit component registry and surface via the
 * SDK's auto-injected component list (the agent already gets that
 * list through the same channel as tool descriptions).
 *
 * Component bodies live in agent-components/ to keep each file under
 * the <200 LOC budget; this entry-point is registration-only.
 */

import { useComponent } from "@copilotkit/react-core/v2";
import { MiniGraphArgs, MiniGraphPreview } from "./agent-components/mini-graph-preview";
import { FindingArgs, FindingCard } from "./agent-components/finding-card";
import { EvalArgs, EvalResult } from "./agent-components/eval-result";

function useMiniGraphPreviewComponent() {
  useComponent({
    name: "mini_graph_preview",
    description:
      "Render a small hop-1 neighborhood snapshot of a graph entity inline in the chat. " +
      "Use when the user wants a visual sanity-check on what's connected to an entity.",
    parameters: MiniGraphArgs,
    render: MiniGraphPreview,
  });
}

function useFindingCardComponent() {
  useComponent({
    name: "finding_card",
    description:
      "Render a single security finding summary inline (severity badge, CWE link, affected resource). " +
      "Use when answering questions about a specific finding by id.",
    parameters: FindingArgs,
    render: FindingCard,
  });
}

function useEvalResultComponent() {
  useComponent({
    name: "eval_result",
    description:
      "Render an eval-run summary inline (pass rate, P/R/F1, agent, duration). " +
      "Use when answering questions about a specific eval run by id.",
    parameters: EvalArgs,
    render: EvalResult,
  });
}

export function AgentComponents() {
  useMiniGraphPreviewComponent();
  useFindingCardComponent();
  useEvalResultComponent();
  return null;
}
