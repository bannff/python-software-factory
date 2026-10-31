"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { AlertCircle, BarChart3 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFocusedRunEntries } from "@/lib/hooks/use-focused-run-entries";
import { useHealth } from "@/lib/hooks/use-health";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";
import { setTimelineFocus } from "@/lib/hooks/use-timeline-focus";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { newestFirst, selectRuntimeMetricEntries, summarizeRuntimeMetrics } from "@/lib/runtime-metrics-summary";
import type { CanvasViewId, TimelineEntry } from "@/lib/types";
import { FocusedRunBanner } from "./focused-run-banner";
import { MetricsNavigationActions } from "./metrics-navigation-actions";
import { RuntimeMetricsCards } from "./runtime-metrics-cards";
import { RuntimeMetricsPanels } from "./runtime-metrics-panels";
import { RuntimeMetricsDrilldown, type DrilldownState } from "./runtime-metrics-drilldown";

interface RuntimeMetricsViewProps { onNavigate?: (viewId: CanvasViewId) => void }

export default function RuntimeMetricsView({ onNavigate }: RuntimeMetricsViewProps) {
  const workbench = useWorkbenchContext();
  const { entries: broadEntries, connected } = useLiveToolStream();
  const focused = useFocusedRunEntries(workbench.focusedRunId);
  const { timeline } = useHealth();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const entries = selectRuntimeMetricEntries(workbench.focusedRunId, focused.entries, broadEntries);
  const summary = useMemo(() => summarizeRuntimeMetrics(entries), [entries]);
  const [drilldown, setDrilldown] = useState<DrilldownState | null>(null);

  useEffect(() => { headingRef.current?.focus(); }, [workbench.navigationRef?.target_ref, workbench.focusedRunId]);
  useEffect(() => { setDrilldown(null); }, [workbench.focusedRunId]);

  const toolCalls = useMemo(() => newestFirst(entries.filter((entry) => entry.type === "tool_call")), [entries]);
  const rlEntries = useMemo(() => newestFirst(entries.filter((entry) => entry.swarmEventType?.startsWith("rl."))), [entries]);
  const failedCalls = useMemo(() => toolCalls.filter((entry) => entry.status === "failed"), [toolCalls]);
  const activeEntries = useMemo(() => newestFirst(entries.filter((entry) => entry.status === "running")), [entries]);
  const slowestCalls = useMemo(() => [...toolCalls].filter((entry) => typeof entry.duration === "number").sort((a, b) => (b.duration ?? 0) - (a.duration ?? 0)).slice(0, 12), [toolCalls]);
  const toggle = (next: DrilldownState) => setDrilldown((current) => current?.key === next.key ? null : next);
  const openTimeline = (rows: TimelineEntry[], title: string, subtitle: string) => {
    setTimelineFocus({ key: `metrics:${title}`, title, subtitle, entryIds: rows.map((entry) => entry.id) });
    onNavigate?.("timeline-v2");
  };

  const focusedState = workbench.focusedRunId && (
    focused.loading ? <MetricsState title="Loading exact run metrics…" />
      : focused.error || !focused.available ? <MetricsState title="Run metrics unavailable." detail={focused.error ?? "The exact attributed Timeline API is unavailable."} error />
      : focused.entries.length === 0 ? <MetricsState title="No attributable runtime metrics." detail="The exact run query succeeded and returned zero attributed Timeline rows." />
      : null
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border/50 bg-card/10 px-4 py-2">
        <BarChart3 className="h-4 w-4 text-sky-400" />
        <div className="min-w-0">
          <h1 ref={headingRef} tabIndex={-1} className="text-xs font-semibold text-foreground/90 outline-none">Runtime Metrics</h1>
          <p className="text-[10px] text-muted-foreground">{workbench.focusedRunId ? "Derived only from exact attributed Timeline data." : "Derived from the retained live timeline buffer."}</p>
        </div>
        <div className="ml-auto flex items-center gap-2 text-[10px]">
          <span className={cn("rounded-full px-2 py-0.5 font-medium", connected ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400")}>{connected ? "live stream connected" : "stream reconnecting"}</span>
          {!workbench.focusedRunId && <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-sky-300">{timeline?.history.available ? "live buffer" : "ephemeral buffer"}</span>}
        </div>
      </div>
      {workbench.focusedRunId && <FocusedRunBanner runId={workbench.focusedRunId} onClear={workbench.clearRunFocus} label="Exact attributed metrics" />}
      <MetricsNavigationActions />
      <div className="flex-1 overflow-auto p-4">
        {focusedState ?? (entries.length === 0 ? <EmptyRuntimeMetrics focused={Boolean(workbench.focusedRunId)} /> : (
          <div className="space-y-4">
            <RuntimeMetricsCards summary={summary} entries={newestFirst(entries)} toolCalls={toolCalls} failedCalls={failedCalls} activeEntries={activeEntries} slowestCalls={slowestCalls} rlEntries={rlEntries} activeKey={drilldown?.key} onToggle={toggle} />
            <AnimatePresence initial={false}>{drilldown && <RuntimeMetricsDrilldown key={drilldown.key} drilldown={drilldown} onOpenTimeline={openTimeline} />}</AnimatePresence>
            <RuntimeMetricsPanels summary={summary} toolCalls={toolCalls} activeKey={drilldown?.key} onToggle={toggle} />
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricsState({ title, detail, error }: { title: string; detail?: string; error?: boolean }) {
  return <div className="flex h-full flex-col items-center justify-center gap-2 text-center">{error ? <AlertCircle className="h-5 w-5 text-amber-400/70" /> : <BarChart3 className="h-6 w-6 text-muted-foreground/30" />}<p className="text-sm text-foreground/80">{title}</p>{detail && <p className="max-w-md text-xs text-muted-foreground">{detail}</p>}</div>;
}
function EmptyRuntimeMetrics({ focused }: { focused: boolean }) {
  return <div className="flex h-full flex-col items-center justify-center gap-3 text-center"><div className="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-500/10"><BarChart3 className="h-6 w-6 text-sky-400/70" /></div><div className="space-y-1"><p className="text-sm text-foreground/80">No runtime telemetry yet.</p><p className="text-xs text-muted-foreground">{focused ? "No exact attributed rows were returned." : "Use chat or trigger tool calls; metrics accumulate from the live stream."}</p></div></div>;
}
