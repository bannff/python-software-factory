"use client";

import type { ReactNode } from "react";
import { Maximize2, RotateCcw, Search } from "lucide-react";
import { NumberTicker } from "@/components/ui/number-ticker";
import type { RunActivity } from "@/lib/run-activity";
import { cn } from "@/lib/utils";

interface GraphToolbarProps {
  query: string;
  searchMode: "type" | "name";
  activePreset: string | null;
  loading: boolean;
  broadControlsDisabled: boolean;
  runsSelector: ReactNode;
  activity: RunActivity;
  onQueryChange: (value: string) => void;
  onToggleSearchMode: () => void;
  onSearch: () => void;
  onLoadPreset: (entityType: string) => void;
  onFit: () => void;
  onReset: () => void;
  stats: { node_count: number; edge_count: number } | null;
  visibleNodes: number;
  visibleLinks: number;
}

const PRESETS: ReadonlyArray<readonly [string, string, keyof RunActivity | null]> = [
  ["Runs", "WorkflowRun", "runs"],
  ["Invocations", "ToolInvocation", "invocations"],
  ["Agents", "Agent", "agents"],
  ["Sessions", "Session", null],
  ["Users", "User", null],
  ["Bricks", "Brick", null],
  ["Memories", "memory", null],
];

export function GraphToolbar(props: GraphToolbarProps) {
  return (
    <div className="flex items-center gap-2 overflow-x-auto border-b border-border/50 bg-card/10 px-4 py-2">
      <div className="relative flex min-w-56 max-w-xs flex-1 items-center gap-1">
        <button onClick={props.onToggleSearchMode} disabled={props.broadControlsDisabled} className="shrink-0 rounded border border-border/50 px-1.5 py-1 text-[10px] font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40">
          {props.searchMode === "type" ? "Type" : "Name"}
        </button>
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={props.query}
            disabled={props.broadControlsDisabled}
            onChange={(event) => props.onQueryChange(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && props.onSearch()}
            placeholder={props.broadControlsDisabled ? "Clear run focus to search broadly" : props.searchMode === "type" ? "Filter by type…" : "Search by name…"}
            className="w-full rounded-lg border border-input bg-background/80 py-1.5 pl-8 pr-3 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/50 disabled:opacity-50"
          />
        </div>
      </div>
      <button onClick={props.onSearch} disabled={props.loading || props.broadControlsDisabled} className="rounded-lg bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-400 transition-colors hover:bg-violet-500/20 disabled:opacity-40">
        {props.loading ? "Loading…" : "Load Graph"}
      </button>
      <div className="flex items-center gap-1">
        {PRESETS.map(([label, entityType, signal]) => {
          const active = props.activePreset === entityType;
          return (
            <button
              key={entityType}
              onClick={() => props.onLoadPreset(entityType)}
              disabled={props.broadControlsDisabled}
              aria-pressed={active}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] transition-colors disabled:opacity-40",
                active
                  ? "border-violet-400/50 bg-violet-500/15 text-violet-200"
                  : "border-border/40 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
              )}
            >
              {signal && props.activity[signal] && <span aria-label={`${label} active`} className="h-1.5 w-1.5 rounded-full bg-emerald-400/80" />}
              {label}
            </button>
          );
        })}
      </div>
      {props.runsSelector}
      <button onClick={props.onFit} title="Fit to view" className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"><Maximize2 className="h-3.5 w-3.5" /></button>
      <button onClick={props.onReset} title="Reload broad graph" className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"><RotateCcw className="h-3.5 w-3.5" /></button>
      {props.stats ? (
        <span className="ml-auto flex shrink-0 items-center gap-2 text-xs text-muted-foreground"><NumberTicker value={props.stats.node_count} className="font-mono text-foreground" /> nodes <span className="text-border/80">·</span> <NumberTicker value={props.stats.edge_count} className="font-mono text-foreground" /> edges</span>
      ) : props.visibleNodes > 0 ? (
        <span className="ml-auto shrink-0 text-xs text-muted-foreground">{props.visibleNodes} nodes · {props.visibleLinks} edges</span>
      ) : null}
    </div>
  );
}
