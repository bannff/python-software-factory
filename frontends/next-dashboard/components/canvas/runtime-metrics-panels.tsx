"use client";

import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimelineEntry } from "@/lib/types";
import type { RuntimeSummary } from "@/lib/runtime-metrics-summary";
import type { DrilldownState } from "./runtime-metrics-drilldown";

export function RuntimeMetricsPanels({ summary, toolCalls, activeKey, onToggle }: {
  summary: RuntimeSummary;
  toolCalls: TimelineEntry[];
  activeKey?: string;
  onToggle: (state: DrilldownState) => void;
}) {
  return (
    <>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_1fr_1fr]">
        <Panel title="Call Volume" subtitle="Tool-call activity across the current source."><SparkBars values={summary.volumeSeries} /></Panel>
        <Panel title="Top Bricks" subtitle="Where attributed work is landing.">
          <RankList items={summary.topBricks} emptyMessage="No brick activity." activeKey={activeKey} prefix="brick" onSelect={(name) => onToggle({ key: `brick:${name}`, title: `Brick: ${name}`, subtitle: `Attributed calls to ${name}.`, entries: toolCalls.filter((entry) => entry.detail === name) })} />
        </Panel>
        <Panel title="Top Tools" subtitle="Most frequently called tools.">
          <RankList items={summary.topTools} emptyMessage="No tool activity." activeKey={activeKey} prefix="tool" onSelect={(name) => onToggle({ key: `tool:${name}`, title: `Tool: ${name}`, subtitle: `Attributed calls to ${name}.`, entries: toolCalls.filter((entry) => entry.title === name) })} />
        </Panel>
      </div>
      <Panel title="Failure Feed" subtitle="Most recent attributed failed tool calls.">
        {summary.recentFailures.length ? (
          <div className="space-y-2">
            {summary.recentFailures.map((entry) => (
              <button key={entry.id} onClick={() => onToggle({ key: `failure:${entry.id}`, title: `Failure: ${entry.title}`, subtitle: `Payload for the failed ${entry.title} call.`, entries: [entry] })}
                className={cn("flex w-full items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-left text-sm transition-colors hover:bg-red-500/10", activeKey === `failure:${entry.id}` && "ring-1 ring-red-500/40")}>
                <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-medium text-red-400">{entry.detail ?? "tool"}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-foreground/85">{entry.title}</span>
                <span className="text-[10px] text-muted-foreground">{entry.error ?? "call failed"}</span>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              </button>
            ))}
          </div>
        ) : <p className="text-sm text-muted-foreground">No failed tool calls in the current source.</p>}
      </Panel>
    </>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return <section className="rounded-xl border border-border/50 bg-card/30 p-4"><div className="mb-3"><h2 className="text-sm font-semibold text-foreground/90">{title}</h2><p className="text-xs text-muted-foreground">{subtitle}</p></div>{children}</section>;
}
function SparkBars({ values }: { values: number[] }) {
  const max = Math.max(...values, 1);
  return <div className="flex h-36 items-end gap-1 rounded-lg bg-background/40 p-3">{values.map((value, index) => <div key={index} className="flex flex-1 flex-col items-center justify-end gap-2"><div className="text-[10px] text-muted-foreground">{value}</div><div className="w-full rounded-sm bg-sky-400/80" style={{ height: `${(value / max) * 100}%` }} /></div>)}</div>;
}
function RankList({ items, emptyMessage, activeKey, prefix, onSelect }: { items: Array<{ name: string; count: number }>; emptyMessage: string; activeKey?: string; prefix: string; onSelect: (name: string) => void }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  return <div className="space-y-2">{items.map((item) => <button key={item.name} onClick={() => onSelect(item.name)} className={cn("flex w-full items-center gap-3 rounded-lg border border-border/40 bg-background/30 px-3 py-2 text-left transition-colors hover:bg-accent/20", activeKey === `${prefix}:${item.name}` && "ring-1 ring-sky-400/40")}><span className="min-w-0 flex-1 truncate font-mono text-xs text-foreground/85">{item.name}</span><span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-300">{item.count}</span><ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" /></button>)}</div>;
}
