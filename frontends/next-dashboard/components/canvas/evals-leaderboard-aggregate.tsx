"use client";

import { useMemo, useState } from "react";
import { useToolData } from "@companion-x/shared-renderer";
import { AlertCircle, ArrowDown, ArrowUp, Inbox, Loader2, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  deriveStatusCounts, filterExperiments, matchesEvalsSearch, sortExperiments,
  type DashboardData, type EvalsFilterMode, type EvalsSortMode,
} from "@/lib/evals-leaderboard-helpers";
import { EvalsLeaderboardRow } from "./evals-leaderboard-row";

const SORT_OPTIONS: Array<{ value: EvalsSortMode; label: string }> = [
  { value: "top_score", label: "Top score" }, { value: "biggest_gain", label: "Biggest gain" },
  { value: "biggest_drop", label: "Biggest drop" }, { value: "newest", label: "Latest completed" },
];
const FILTER_OPTIONS: EvalsFilterMode[] = ["all", "improved", "regressed", "baseline"];

export function EvalsLeaderboardAggregate({ onRunSelect }: { onRunSelect: (runId: string) => void }) {
  const { data, loading, error } = useToolData("evals_get_dashboard_summary");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortMode, setSortMode] = useState<EvalsSortMode>("top_score");
  const [filterMode, setFilterMode] = useState<EvalsFilterMode>("all");
  const dashboard = data as DashboardData | null;
  const { experiments, counts } = useMemo(() => {
    if (!dashboard?.experiments) return { experiments: [], counts: { improved: 0, regressed: 0, steady: 0, baseline: 0 } };
    let rows = filterExperiments(dashboard.experiments, filterMode);
    if (searchQuery) rows = rows.filter((row) => matchesEvalsSearch(row, searchQuery));
    return { experiments: sortExperiments(rows, sortMode), counts: deriveStatusCounts(dashboard.experiments) };
  }, [dashboard, filterMode, searchQuery, sortMode]);

  if (loading) return <div className="flex h-full items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>;
  if (error) return <div className="flex h-full flex-col items-center justify-center gap-2 px-6"><AlertCircle className="h-5 w-5 text-destructive/60" /><p className="max-w-sm text-sm text-muted-foreground">{error}</p></div>;
  if (!dashboard?.experiments?.length) return <div className="flex h-full flex-col items-center justify-center gap-2"><Inbox className="h-5 w-5 text-muted-foreground/50" /><p className="text-sm text-muted-foreground">No experiments yet. Run an eval to see your leaderboard.</p></div>;

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 flex-col gap-1.5 border-b border-border/20 px-3 py-2">
        <div className="flex items-center gap-3 text-[11px]"><span className="text-muted-foreground"><b className="text-foreground/80">{dashboard.overview.experiments}</b> experiments · <b className="text-foreground/80">{dashboard.overview.saved_configs}</b> configs</span><div className="flex-1" />{counts.improved > 0 && <span className="inline-flex items-center text-[10px] font-medium text-emerald-400"><ArrowUp className="h-2.5 w-2.5" />{counts.improved} improved</span>}{counts.regressed > 0 && <span className="inline-flex items-center text-[10px] font-medium text-red-400"><ArrowDown className="h-2.5 w-2.5" />{counts.regressed} regressed</span>}</div>
        <div className="text-[10px] text-muted-foreground/60">Persisted terminal results only. Live evaluator activity appears in Timeline.</div>
        <div className="flex items-center gap-2">
          <div className="relative max-w-xs flex-1"><Search className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" /><Input type="search" aria-label="Search experiments" placeholder="Search model, technique, experiment…" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} className="h-7 border-border/30 bg-background/50 pl-7 pr-2 text-[11px]" /></div>
          <div className="flex overflow-hidden rounded border border-border/30" role="group" aria-label="Sort order">{SORT_OPTIONS.map((option) => <button key={option.value} onClick={() => setSortMode(option.value)} aria-pressed={sortMode === option.value} className={cn("px-2 py-1 text-[10px] transition-colors", sortMode === option.value ? "bg-sky-500/15 font-medium text-sky-300" : "text-muted-foreground hover:bg-accent/20 hover:text-foreground")}>{option.label}</button>)}</div>
        </div>
        <div className="flex items-center gap-1">{FILTER_OPTIONS.map((filter) => <button key={filter} onClick={() => setFilterMode(filter)} aria-pressed={filterMode === filter} className={cn("rounded px-2 py-0.5 text-[10px] capitalize transition-colors", filterMode === filter ? "border border-border/30 bg-white/8 text-foreground/80" : "text-muted-foreground hover:bg-accent/30 hover:text-foreground")}>{filter}</button>)}</div>
      </div>
      <div className="flex-1 overflow-y-auto px-1 py-2"><div className="mx-auto max-w-2xl">{experiments.length ? experiments.map((experiment) => <EvalsLeaderboardRow key={experiment.experiment_name} exp={experiment} onRunSelect={onRunSelect} />) : <div className="py-8 text-center text-sm text-muted-foreground">No experiments match your filters.</div>}</div></div>
    </div>
  );
}
