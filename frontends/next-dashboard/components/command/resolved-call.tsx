"use client";

/**
 * The resolved MCP call, shown BEFORE submit (bd:3jcls.4).
 *
 * The highest-value part of the palette, and the reason it teaches rather than
 * just executes: the human sees the exact tool name and argument object that
 * will run — which is also precisely what they would otherwise have to know
 * how to ask the assistant for. The ML Overview's "Ask the assistant to run
 * the relevant MCP operation" is only actionable if the UI has told you what
 * the operation is called.
 */

import { cn } from "@/lib/utils";

interface ResolvedCallProps {
  /** Owning brick — the first argument of the call, not decoration. */
  brick: string;
  tool: string;
  args: Record<string, unknown>;
  /** Required params still blank — the call is shown but not yet valid. */
  missing: string[];
}

export function ResolvedCall({ brick, tool, args, missing }: ResolvedCallProps) {
  const body = JSON.stringify(args, null, 2);
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Resolved call
        </span>
        {missing.length > 0 && (
          <span className="text-[10px] text-amber-500/90" role="status">
            needs {missing.join(", ")}
          </span>
        )}
      </div>
      <pre
        data-testid="resolved-call"
        className={cn(
          "overflow-x-auto rounded-sm border border-border/60 bg-card/40 p-2",
          "font-mono text-[11px] leading-relaxed text-foreground",
        )}
      >
        {/* Shaped like the `call_brick_tool(brick, tool, args)` invocation the
            human would otherwise have to compose by hand — the palette teaching
            its own escape hatch. */}
        <code>
          <span className="text-muted-foreground">call_brick_tool</span>(
          <span className="text-foreground">{brick}</span>,{" "}
          <span className="text-foreground">{tool}</span>,{" "}
          {body === "{}" ? "{}" : body})
        </code>
      </pre>
    </div>
  );
}
