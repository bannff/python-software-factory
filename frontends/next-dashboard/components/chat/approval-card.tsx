"use client";

/**
 * <ApprovalCard /> — inline human-in-the-loop approval card rendered by
 * CopilotKit v2's `useHumanInTheLoop` hook for destructive tools
 * (bd-xpxa).
 *
 * The hook auto-renders this card in the chat stream when one of the
 * gated tools is about to fire. The agent waits on the user's response
 * (`respond({approve, reason})`) before proceeding.
 *
 * Visual shape mirrors the existing <ToolCallCard> shell (border,
 * padding, status pill area) but uses an amber-orange "needs human
 * attention" accent so it pops against violet (FE) and gray (BE) tool
 * cards. Two prominent buttons (Approve / Deny). Args are previewed
 * inline so the user can verify before clicking.
 *
 * "executing" status = agent is waiting on us; render Approve/Deny.
 * "complete"  status = decision was already made; render the verdict.
 * "inProgress" status = args are still streaming; show a loading hint.
 */

import { Loader2, ShieldAlert, ThumbsUp, ThumbsDown, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type ApprovalStatus = "inProgress" | "executing" | "complete";

interface ApprovalCardProps {
  /** Tool name as emitted on the wire. */
  tool: string;
  /** Decoded arguments (Zod-validated by the hook). */
  args: Record<string, unknown> | undefined;
  /** Current status from the v2 hook. */
  status: ApprovalStatus;
  /** Approve callback — wired to the hook's `respond({approve:true})`. */
  onApprove?: () => void;
  /** Deny callback — wired to the hook's `respond({approve:false})`. */
  onDeny?: () => void;
  /** Hook-provided result string (set when status==='complete'). */
  result?: string;
}

function formatArgs(args: Record<string, unknown> | undefined): string {
  if (!args || Object.keys(args).length === 0) return "(no arguments)";
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

function parseDecision(result: string | undefined): { approved?: boolean } {
  if (!result) return {};
  try {
    const v = JSON.parse(result);
    if (v && typeof v === "object" && "approve" in v) {
      return { approved: Boolean((v as { approve: unknown }).approve) };
    }
  } catch {
    // string result, no decision parse
  }
  return {};
}

export function ApprovalCard({
  tool,
  args,
  status,
  onApprove,
  onDeny,
  result,
}: ApprovalCardProps) {
  const waiting = status === "executing";
  const streaming = status === "inProgress";
  const done = status === "complete";
  const decision = parseDecision(result);

  return (
    <div
      data-testid="approval-card"
      data-tool={tool}
      data-status={status}
      className={cn(
        "ml-11 my-2 rounded-xl border bg-card/80 backdrop-blur-sm overflow-hidden shadow-sm",
        "border-amber-500/50 shadow-amber-500/5",
      )}
    >
      <div className="flex items-center justify-between gap-3 px-3 py-2 border-b border-amber-500/20 bg-amber-500/[0.04]">
        <div className="flex items-center gap-2 min-w-0">
          <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500 dark:text-amber-300" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-amber-700 dark:text-amber-200 truncate">
                Approval required
              </span>
              <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
                Destructive
              </span>
            </div>
            <code className="block truncate text-[11px] font-mono text-foreground/70">
              {tool}
            </code>
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium",
            waiting && "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/30",
            streaming && "bg-muted/60 text-muted-foreground border-border",
            done && (decision.approved
              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/30"
              : "bg-red-500/15 text-red-600 dark:text-red-300 border-red-500/30"),
          )}
        >
          {streaming && <Loader2 className="h-3 w-3 animate-spin" />}
          {waiting && "Awaiting"}
          {streaming && "Loading…"}
          {done && (decision.approved ? "Approved" : "Denied")}
        </span>
      </div>

      <div className="p-3 space-y-3">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
            Arguments
          </div>
          <pre className="max-h-40 overflow-auto rounded-md bg-muted/40 p-2 text-[11px] leading-relaxed text-foreground/80 whitespace-pre-wrap break-words">
            {formatArgs(args)}
          </pre>
        </div>

        {waiting && (
          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              data-testid="approval-deny"
              onClick={onDeny}
              className={cn(
                "flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                "border-border bg-background hover:bg-muted/60 hover:border-red-500/40 hover:text-red-600 dark:hover:text-red-300",
              )}
            >
              <ThumbsDown className="h-3.5 w-3.5" /> Deny
            </button>
            <button
              type="button"
              data-testid="approval-approve"
              onClick={onApprove}
              className={cn(
                "flex-1 inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20",
              )}
            >
              <ThumbsUp className="h-3.5 w-3.5" /> Approve
            </button>
          </div>
        )}

        {done && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            {decision.approved ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                <span>You approved this call. The agent will proceed.</span>
              </>
            ) : (
              <>
                <XCircle className="h-3.5 w-3.5 text-red-500" />
                <span>You denied this call. The agent will stop or pivot.</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
