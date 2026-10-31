"use client";

/**
 * Sub-agent containment box (bd:python-factory-esb6n).
 *
 * Groups everything a single `spawn_subagent` produces — its tool-call
 * pills (via the chrome-less SubAgentToolRows the spawn renderer now
 * emits), its reasoning ("Thinking") panel, and its prose output — into
 * ONE collapsible bordered box per spawn. The box owns the single header
 * ("Sub-agent · {agent_id}"); the inline spawn renderer sheds its own
 * ToolCallCard chrome so there is exactly one border and one header
 * (meta-architect verdict 69cf6476, option b). Coordinator (parent-agent)
 * content renders bare, full-width, outside any box, so the boundary is
 * spatial and absolute: inside the border = sub-agent, outside =
 * coordinator.
 *
 * The pure partition logic lives in `sub-agent-grouping.ts`
 * (`groupMessageElements`); this module is the React rendering shell.
 *
 * Seam: CopilotChatMessageView `children` render-prop, which hands us
 * { messageElements, messages, isRunning, interruptElement }. We re-emit
 * interruptElement + the running cursor because the children branch
 * early-returns before the default branch renders them (guardrail #2).
 */

import { useState, type ReactElement } from "react";
import type { Message } from "@ag-ui/core";
import { Bot, ChevronRight, GitBranch, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { groupMessageElements } from "./sub-agent-grouping";

// ---- box component --------------------------------------------------------

/** Pick the header icon from the box label prefix (set by spawnBoxLabel). */
function labelIcon(label: string) {
  if (label.startsWith("Swarm")) return Users;
  if (label.startsWith("Pipeline")) return GitBranch;
  return Bot;
}

function SubAgentGroup({
  agentId,
  children,
}: {
  /** The full box header label, e.g. "Sub-agent · eval-runner" or "Swarm · 2 agents". */
  agentId: string;
  children: ReactElement[];
}) {
  const [open, setOpen] = useState(true);
  const Icon = labelIcon(agentId);
  return (
    <div
      className={cn(
        "ml-11 my-2 rounded-xl border border-border/60 border-l-[3px] border-l-blue-500/60",
        "bg-blue-500/[0.03] dark:bg-blue-400/[0.04] overflow-hidden",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-accent/30 transition-colors"
      >
        <ChevronRight
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-90",
          )}
        />
        <Icon className="h-3.5 w-3.5 shrink-0 text-blue-500/80" />
        <span className="truncate text-xs font-medium text-foreground/80">
          {agentId}
        </span>
      </button>
      {open && <div className="px-1 pb-1">{children}</div>}
    </div>
  );
}

// ---- grouped view (children render-prop body) -----------------------------

interface GroupedViewProps {
  messageElements: ReactElement[];
  messages: Message[];
  isRunning: boolean;
  interruptElement: ReactElement | null;
}

/**
 * Body for `CopilotChatMessageView`'s `children` render-prop. Renders
 * coordinator elements bare and each sub-agent run inside a SubAgentGroup
 * box, then re-emits the interrupt element + running cursor (guardrail #2).
 */
export function SubAgentGroupedView({
  messageElements,
  messages,
  isRunning,
  interruptElement,
}: GroupedViewProps) {
  const runs = groupMessageElements(messages, messageElements);
  const last = messages[messages.length - 1];
  const showCursor = isRunning && last?.role !== "reasoning";

  return (
    <div
      data-testid="copilot-message-list"
      className="copilotKitMessages cpk:flex cpk:flex-col"
    >
      {runs.map((run) =>
        run.kind === "coordinator" ? (
          run.element
        ) : (
          <SubAgentGroup key={run.key} agentId={run.agentId}>
            {run.elements}
          </SubAgentGroup>
        ),
      )}
      {interruptElement}
      {showCursor && (
        <div className="cpk:mt-2">
          <div className="cpk:w-[11px] cpk:h-[11px] cpk:rounded-full cpk:bg-foreground cpk:animate-pulse-cursor cpk:ml-1" />
        </div>
      )}
    </div>
  );
}
