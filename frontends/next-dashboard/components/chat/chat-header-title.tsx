"use client";

import { MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

interface LiveTool { label: string; title: string; connected: boolean }

/** Icon-led left side of the chat header: chat icon, active view, live tool. */
export function ChatHeaderTitle({ viewLabel, tool }: { viewLabel?: string; tool?: LiveTool }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" aria-label="Chat" role="img" />
      {viewLabel && <span className="truncate text-[10px] text-muted-foreground/70">{viewLabel}</span>}
      {tool && (
        <>
          <span className="shrink-0 text-border/50">·</span>
          <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full",
            tool.connected ? "animate-pulse bg-emerald-400" : "bg-muted-foreground/40")} />
          <span data-testid="live-tool" title={tool.title}
            className="max-w-[120px] truncate text-[10px] text-muted-foreground/70">{tool.label}</span>
        </>
      )}
    </div>
  );
}
