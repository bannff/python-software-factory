"use client";

import { useState, type ReactNode } from "react";
import {
  Root as CollapsibleRoot,
  Trigger as CollapsibleTrigger,
  Content as CollapsibleContent,
} from "@radix-ui/react-collapsible";
import { ChevronRight, Loader2, MonitorCog } from "lucide-react";
import { cn } from "@/lib/utils";

type ToolStatus = "inProgress" | "executing" | "complete";

interface ToolCallCardProps {
  /** Tool name as emitted on the wire. */
  name: string;
  /** Current execution status from the v2 render hook. */
  status: ToolStatus;
  /** Optional label override; defaults to the tool name. */
  title?: string;
  /** Optional icon to render inside the status pill. */
  icon?: ReactNode;
  /**
   * One-line preview rendered under the title in the collapsed state
   * (bd-rx48 / D3). Examples: ``3 results · "Auth bypass…"`` or
   * ``key=session-42 · HIT`` so the user gets signal without expanding.
   */
  previewLine?: ReactNode;
  /** Body slot — args, result preview, or rich card content. */
  children?: ReactNode;
}

const STATUS_LABEL: Record<ToolStatus, string> = {
  inProgress: "Running",
  executing: "Running",
  complete: "Done",
};

const STATUS_PILL: Record<ToolStatus, string> = {
  inProgress:
    "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/20",
  executing:
    "bg-amber-500/15 text-amber-600 dark:text-amber-300 border-amber-500/20",
  complete:
    "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/20",
};

/**
 * Kiro / VS Code Copilot Chat-style collapsible tool card.
 *
 * Shared by every CopilotKit v2 tool renderer (per-tool + wildcard) so
 * that running tools render as identical pills with consistent chrome.
 * Renderers pass their rich body via `children` and an optional
 * `previewLine` for the collapsed state. v2 status semantics map
 * directly onto the badge.
 *
 * When the tool name starts with ``fe_`` (CopilotKit frontend tool, the
 * round-trip lives in `useFrontendTool`), the card gets a violet accent
 * and a monitor icon so users can tell apart things that ran on their
 * machine from things that ran on the backend (bd-f849 / D4).
 */
export function ToolCallCard({
  name,
  status,
  title,
  icon,
  previewLine,
  children,
}: ToolCallCardProps) {
  const [open, setOpen] = useState(false);
  const running = status !== "complete";
  const hasBody = Boolean(children);
  const isFrontendTool = name.startsWith("fe_");
  const resolvedIcon = icon ?? (isFrontendTool
    ? <MonitorCog className="h-3.5 w-3.5" />
    : null);

  return (
    <CollapsibleRoot
      open={open}
      onOpenChange={setOpen}
      className={cn(
        "ml-11 my-2 rounded-xl border bg-card/50 backdrop-blur-sm overflow-hidden shadow-sm",
        isFrontendTool
          ? "border-violet-500/40 shadow-violet-500/5"
          : "border-border/50",
      )}
    >
      <CollapsibleTrigger
        disabled={!hasBody}
        className={cn(
          "flex w-full items-center justify-between gap-3 px-3 py-2 text-left",
          hasBody && "hover:bg-accent/40 transition-colors cursor-pointer",
          !hasBody && "cursor-default",
        )}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {hasBody && (
            <ChevronRight
              className={cn(
                "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                open && "rotate-90",
              )}
            />
          )}
          {resolvedIcon && (
            <span className={cn(
              "shrink-0",
              isFrontendTool ? "text-violet-500 dark:text-violet-300" : "text-muted-foreground",
            )}>
              {resolvedIcon}
            </span>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 min-w-0">
              <span className={cn(
                "truncate text-xs font-medium",
                isFrontendTool ? "text-violet-600 dark:text-violet-200" : "text-foreground/90",
              )}>
                {title ?? name}
              </span>
              {isFrontendTool && (
                <span className="shrink-0 rounded-full bg-violet-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
                  Frontend
                </span>
              )}
            </div>
            {previewLine && (
              <div className="mt-0.5 truncate text-[11px] text-muted-foreground/80">
                {previewLine}
              </div>
            )}
          </div>
        </div>
        <span
          className={cn(
            "shrink-0 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium",
            STATUS_PILL[status],
          )}
        >
          {running && <Loader2 className="h-3 w-3 animate-spin" />}
          {STATUS_LABEL[status]}
        </span>
      </CollapsibleTrigger>
      {hasBody && (
        <CollapsibleContent className="border-t border-border/50">
          <div className="p-4">{children}</div>
        </CollapsibleContent>
      )}
    </CollapsibleRoot>
  );
}

/**
 * Safe JSON.parse for v2 `result` strings — backend serializes via
 * `json.dumps`, so values may be objects, arrays, or primitives.
 * Returns the raw string if parsing fails.
 */
export function parseResult(result: string | undefined): unknown {
  if (result == null) return undefined;
  try {
    return JSON.parse(result);
  } catch {
    return result;
  }
}
