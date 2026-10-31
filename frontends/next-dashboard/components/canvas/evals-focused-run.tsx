"use client";

import { AlertCircle, Beaker, Inbox, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFocusedEvalResult } from "@/lib/hooks/use-focused-eval-result";
import { FocusedRunBanner } from "./focused-run-banner";

export function EvalsFocusedRun({ runId, onClear }: { runId: string; onClear: () => void }) {
  const { refresh, ...state } = useFocusedEvalResult(runId);
  const result = state.result;
  const hasResultData = result !== null && Object.keys(result).length > 0;
  const cases = result?.case_results ?? [];
  const total = Number(result?.total_cases ?? cases.length);
  const passed = Number(result?.passed_cases ?? result?.passed ?? cases.filter((item) => item.passed).length);
  const score = Number(result?.avg_score ?? (total ? cases.reduce((sum, item) => sum + Number(item.score ?? 0), 0) / total : 0));
  const passRate = Number(result?.pass_rate ?? (total ? passed / total : 0));

  return (
    <div className="flex h-full flex-col">
      <FocusedRunBanner runId={runId} onClear={onClear} label="Exact evaluation artifact" />
      {state.loading ? <State icon={<Loader2 className="h-5 w-5 animate-spin" />} title={state.waiting ? "Waiting for exact evaluation artifact…" : "Loading exact eval artifact…"} detail={state.waiting ? "No attributable eval artifact has been persisted yet. Automatic evaluation runs in the background; rechecking this exact workflow run." : undefined} />
        : state.error ? <State icon={<AlertCircle className="h-5 w-5 text-amber-400/70" />} title="Eval artifact unavailable." detail={state.error} />
        : !state.found ? <State icon={<Inbox className="h-5 w-5 text-muted-foreground/50" />} title="No attributable eval artifact." detail="The exact run lookup succeeded but found no persisted evaluation result." action={<button type="button" aria-label="Refresh exact evaluation artifact" onClick={refresh} className="inline-flex items-center gap-1.5 rounded-md border border-border/50 px-2.5 py-1.5 text-xs font-medium text-foreground/80 transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><RefreshCw className="h-3.5 w-3.5" />Refresh exact artifact</button>} />
        : !hasResultData ? <State icon={<Beaker className="h-5 w-5 text-muted-foreground/50" />} title="Attributable eval artifact is empty." detail="A persisted result exists for this run, but it contains no result fields." />
        : (
          <div className="flex-1 overflow-auto p-4">
            <div className="mx-auto max-w-3xl space-y-4">
              <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Metric label="Verdict" value={String(result?.verdict ?? "recorded")} tone={String(result?.verdict).toUpperCase() === "PASS" ? "good" : "bad"} />
                <Metric label="Pass rate" value={`${Math.round(passRate * 100)}%`} />
                <Metric label="Cases" value={`${passed}/${total}`} />
                <Metric label="Average score" value={score.toFixed(2)} />
              </section>
              <section className="overflow-hidden rounded-xl border border-border/50 bg-card/30">
                <div className="border-b border-border/30 px-4 py-3"><h2 className="text-sm font-semibold text-foreground/90">Exact case results</h2><p className="text-xs text-muted-foreground">Only cases persisted on this workflow run are shown.</p></div>
                <div className="divide-y divide-border/20">{cases.length ? cases.map((item, index) => <div key={index} className="flex items-start gap-3 px-4 py-3 text-xs"><span className={cn("mt-0.5", item.passed ? "text-emerald-400" : "text-red-400")}>{item.passed ? "✓" : "✗"}</span><div className="min-w-0 flex-1"><p className="font-mono text-foreground/85">{String(item.case_name ?? `case-${index}`)}</p>{item.reason != null && <p className="mt-1 text-muted-foreground">{String(item.reason)}</p>}</div><span className="font-mono text-muted-foreground">{Number(item.score ?? 0).toFixed(2)}</span></div>) : <p className="px-4 py-3 text-xs text-muted-foreground">No case rows were persisted with this attributable summary.</p>}</div>
              </section>
            </div>
          </div>
        )}
    </div>
  );
}

function State({ icon, title, detail, action }: { icon: React.ReactNode; title: string; detail?: string; action?: React.ReactNode }) {
  return <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">{icon}<p className="text-sm text-foreground/80">{title}</p>{detail && <p className="max-w-md text-xs text-muted-foreground">{detail}</p>}{action}</div>;
}
function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  return <div className="rounded-xl border border-border/50 bg-card/30 p-3"><p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p><p className={cn("mt-1 font-mono text-lg font-semibold", tone === "good" ? "text-emerald-400" : tone === "bad" ? "text-red-400" : "text-foreground/90")}>{value}</p></div>;
}
