"use client";

import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import { useToolData } from "@companion-x/shared-renderer";
import { ArrowDown, ArrowUp, ChevronRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { completionLabel, decomposeExperimentName, type ExperimentSummary } from "@/lib/evals-leaderboard-helpers";
import { EntityChip } from "./entity-chip";

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const max = Math.max(...points, 1), min = Math.min(...points, 0), range = max - min || 1;
  const coords = points.map((value, index) => `${(index / (points.length - 1)) * 64},${20 - ((value - min) / range) * 20}`);
  return <svg viewBox="0 0 64 20" width={64} height={20} className="shrink-0 text-sky-400/60" aria-hidden="true"><polyline points={coords.join(" ")} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
function formatWhen(iso: string): string {
  const timestamp = new Date(iso).getTime();
  if (!Number.isFinite(timestamp)) return "";
  const age = Date.now() - timestamp;
  if (age < 60_000) return "just now";
  if (age < 3_600_000) return `${Math.round(age / 60_000)}m ago`;
  if (age < 86_400_000) return `${Math.round(age / 3_600_000)}h ago`;
  return `${Math.round(age / 86_400_000)}d ago`;
}

function DrillDownPanel({ runId }: { runId: string }) {
  const { data, loading, error } = useToolData("evals_get_run_result", { run_id: runId });
  if (loading) return <div className="py-3 text-center text-[10px] text-muted-foreground"><Loader2 className="inline h-3 w-3 animate-spin" /> Loading run…</div>;
  if (error) return <div className="py-2 text-center text-[10px] text-red-400">{error}</div>;
  if (!data) return null;
  const result = data as Record<string, unknown>;
  const cases = (result.case_results ?? []) as Array<Record<string, unknown>>;
  const passed = Number(result.passed_cases ?? result.passed ?? cases.filter((item) => item.passed).length);
  const total = Number(result.total_cases ?? cases.length);
  const score = Number(result.avg_score ?? (total ? cases.reduce((sum, item) => sum + Number(item.score ?? 0), 0) / total : 0));
  return (
    <div className="mb-1 ml-[34px] mt-1 rounded-lg border border-border/30 bg-accent/[0.04] px-3 py-2 text-[10px]">
      <div className="mb-2 flex items-center gap-4 text-muted-foreground"><span><b className="text-foreground/80">{total ? Math.round((passed / total) * 100) : 0}%</b> pass rate</span><span>{passed}/{total} cases</span><span>avg <b className="text-foreground/80">{score.toFixed(2)}</b></span></div>
      <div className="max-h-48 space-y-1 overflow-y-auto">{cases.map((item, index) => <div key={index} className="flex items-start gap-2 border-b border-border/10 py-0.5 last:border-0"><span className={item.passed ? "text-emerald-400" : "text-red-400"}>{item.passed ? "✓" : "✗"}</span><span className="min-w-[100px] font-mono text-foreground/70">{String(item.case_name ?? `case-${index}`)}</span><span className="text-muted-foreground">{Number(item.score ?? 0).toFixed(1)}</span><span className="flex-1 truncate text-muted-foreground/50">{String(item.reason ?? "")}</span></div>)}</div>
    </div>
  );
}

export function EvalsLeaderboardRow({ exp, onRunSelect }: { exp: ExperimentSummary; onRunSelect: (runId: string) => void }) {
  const [open, setOpen] = useState(false);
  const chips = decomposeExperimentName(exp.experiment_name);
  const delta = exp.pass_rate_delta;
  const hasDelta = delta != null && exp.regression_state !== "baseline";
  const deltaPoints = hasDelta ? Math.round(Math.abs(delta) * 100) : 0;
  const verdict = exp.latest_verdict === "PASS" ? "border-emerald-500" : exp.latest_verdict === "FAIL" ? "border-red-500" : "border-gray-500";
  const insight = exp.regression_state === "improved" ? `Improved +${deltaPoints}pts` : exp.regression_state === "regressed" ? `Regressed -${deltaPoints}pts · ${exp.latest_failed_cases} failing` : null;

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <div className="flex items-stretch">
        <div className="relative flex w-[34px] shrink-0 flex-col items-center"><div className="absolute left-1/2 top-0 h-[18px] w-[1.5px] -translate-x-1/2 bg-border/50" /><div className={cn("relative z-10 mt-[14px] h-[10px] w-[10px] rounded-full border-[2.5px] bg-background", verdict)} /><div className="absolute bottom-0 left-1/2 top-[26px] w-[1.5px] -translate-x-1/2 bg-border/50" /></div>
        <div className={cn("my-[3px] min-w-0 flex-1 rounded-xl border border-border/40 px-3 py-2 transition-all hover:border-border/70", open && "border-sky-500/40 bg-sky-500/[0.03]", exp.latest_verdict === "FAIL" && !open && "border-red-500/20 bg-red-500/[0.02]")}>
          <div className="flex items-center gap-2">
            <Collapsible.Trigger asChild><button aria-label={`Toggle details for ${exp.experiment_name}`} className="flex min-w-0 flex-1 items-center gap-1.5 rounded text-left focus-visible:ring-2 focus-visible:ring-sky-400/60"><ChevronRight className={cn("h-3 w-3 shrink-0 text-muted-foreground/60 transition-transform", open && "rotate-90")} /><span className="flex min-w-0 flex-wrap items-center gap-1">{chips.map((chip) => <span key={chip} className="rounded bg-sky-500/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-sky-300">{chip.length > 20 ? `${chip.slice(0, 20)}…` : chip}</span>)}</span></button></Collapsible.Trigger>
            <div className="flex shrink-0 items-center gap-2">{exp.agent?.model_id && <EntityChip kind="brick" value={exp.agent.model_id.split("/").pop()?.slice(0, 12) ?? ""} />}<Sparkline points={exp.recent_pass_rates} /><span className="w-10 text-right font-mono text-sm font-semibold tabular-nums">{Math.round(exp.latest_pass_rate * 100)}%</span>{hasDelta ? <span className={cn("flex w-8 items-center text-[10px]", exp.regression_state === "improved" ? "text-emerald-400" : "text-red-400")}>{exp.regression_state === "improved" ? <ArrowUp className="h-2.5 w-2.5" /> : <ArrowDown className="h-2.5 w-2.5" />}{deltaPoints}</span> : <span className="w-8 text-center text-[10px] text-muted-foreground/40">—</span>}<span className="w-14 text-right text-[10px] text-muted-foreground/50">{exp.latest_timestamp ? formatWhen(exp.latest_timestamp) : completionLabel(exp)}</span></div>
          </div>
        </div>
      </div>
      <Collapsible.Content className="overflow-hidden data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up">
        {insight && <div className={cn("ml-[34px] px-3 py-1 text-[10px] font-medium", exp.regression_state === "improved" ? "text-emerald-400" : "text-red-400")}>{insight}</div>}
        {open && exp.latest_run_id && <DrillDownPanel runId={exp.latest_run_id} />}
        {exp.latest_run_id && <div className="ml-[34px] px-3 pb-1"><EntityChip kind="run" value={exp.latest_run_id.slice(0, 8)} onClick={(event) => { event.stopPropagation(); onRunSelect(exp.latest_run_id); }} /></div>}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
