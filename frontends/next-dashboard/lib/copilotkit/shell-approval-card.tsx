"use client";

/**
 * ShellApprovalCard — HITL approval UI for shell / python_repl tool calls.
 *
 * Rendered by useHumanInTheLoop("fe_approve_shell") in frontend-tools.tsx.
 * CopilotKit drives the card lifecycle by status:
 *   - "inProgress" — tool call streaming in; show command, no buttons yet
 *     (respond not available)
 *   - "executing"  — agent paused, waiting for the human; show Approve/Deny.
 *     Clicking calls onDecision(approved) → respond({approved, tool, command})
 *     which resolves the tool-call so the Strands agent resumes.
 *   - "complete"   — decision settled; show the outcome chip.
 *
 * The agent's ShellApprovalPlugin (backend) reads {approved} from the
 * tool result in message history and lets shell through (or blocks it).
 *
 * Design: amber = "something wants to run on your machine"; monospace
 * command preview; Deny left / Approve right so Approve is deliberate.
 */

import { Terminal, ShieldAlert, Check, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type ToolStatus = "inProgress" | "executing" | "complete";

interface ShellApprovalCardProps {
  tool: string;
  command: string;
  status: ToolStatus;
  /** Called when the user clicks Approve (true) or Deny (false). */
  onDecision: (approved: boolean) => void;
}

export function ShellApprovalCard({
  tool,
  command,
  status,
  onDecision,
}: ShellApprovalCardProps) {
  const decided = status === "complete";
  const awaiting = status === "executing"; // respond is live now

  return (
    <div
      className={cn(
        "ml-11 my-2 rounded-xl border overflow-hidden",
        decided
          ? "border-border/60 bg-muted/10"
          : "border-amber-500/50 bg-amber-500/[0.04]",
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-amber-500/20">
        <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-500" />
        <span className="text-xs font-semibold text-amber-600 dark:text-amber-400">
          Tool approval requested
        </span>
        <span className="ml-auto text-[10px] text-muted-foreground font-mono bg-muted/50 px-1.5 py-0.5 rounded">
          {tool}
        </span>
      </div>

      {/* Command preview */}
      <div className="px-3 py-2">
        <div className="flex items-start gap-2">
          <Terminal className="h-3.5 w-3.5 shrink-0 text-muted-foreground mt-0.5" />
          <pre className="text-[11px] font-mono text-foreground/90 whitespace-pre-wrap break-all leading-relaxed max-h-32 overflow-y-auto">
            {command || "(no command)"}
          </pre>
        </div>
        <p className="mt-1.5 text-[10px] text-muted-foreground">
          This tool will run with the arguments shown above.
        </p>
      </div>

      {/* Actions / outcome */}
      {awaiting ? (
        <div className="flex border-t border-border/40">
          <button
            type="button"
            onClick={() => onDecision(false)}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
            Deny
          </button>
          <div className="w-px bg-border/40" />
          <button
            type="button"
            onClick={() => onDecision(true)}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
          >
            <Check className="h-3.5 w-3.5" />
            Approve
          </button>
        </div>
      ) : decided ? (
        <div className="px-3 py-2 text-[11px] font-medium border-t border-border/40 text-muted-foreground">
          Decision recorded
        </div>
      ) : (
        <div className="flex items-center gap-1.5 px-3 py-2 text-[11px] border-t border-border/40 text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          Preparing approval…
        </div>
      )}
    </div>
  );
}
