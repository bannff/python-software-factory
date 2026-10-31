"use client";

/**
 * <EvalResult /> — agent-summonable eval-run summary
 * (bd-kzsl Phase 1, component 3/3).
 *
 * Reads `evals_list_run_results` (same shape welcome-view consumes).
 * Tries the run id; falls back to `latest` so the card never renders
 * empty when the agent passes a stale id.
 */

import { useEffect, useState } from "react";
import { Beaker, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { z } from "zod";
import { callTool } from "@/lib/api";
import { unwrap } from "./_shared";

export const EvalArgs = z.object({
  run_id: z.string().describe("The eval run id to summarise."),
});

interface EvalLatest {
  run_id?: string;
  pass_rate?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  agent_name?: string;
  agent?: string;
  duration_seconds?: number;
  duration?: number;
}

function Metric({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-md border border-border/50 bg-background/50 px-2 py-1">
      <div className="text-muted-foreground uppercase tracking-wide">{label}</div>
      <div className="text-foreground/90 font-medium tabular-nums">
        {value != null ? value.toFixed(2) : "—"}
      </div>
    </div>
  );
}

export function EvalResult({ run_id }: z.infer<typeof EvalArgs>) {
  const [data, setData] = useState<EvalLatest | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await callTool("evals_list_run_results", {});
        if (cancelled) return;
        const result = unwrap(raw) as Record<string, unknown> | undefined;
        const latest = (result?.latest ?? null) as EvalLatest | null;
        const runs = (result?.runs ?? result?.results ?? []) as EvalLatest[];
        const match = runs.find((r) => r.run_id === run_id) ?? latest;
        setData(match ?? null);
      } catch {
        // swallow — render the empty state
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [run_id]);

  const passRate = data?.pass_rate;
  const passed = passRate != null && passRate >= 0.5;

  return (
    <div className="ml-11 my-2 rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/50">
        <Beaker className="h-3.5 w-3.5 text-blue-500" />
        <span className="text-xs font-medium text-foreground/90">Eval run</span>
        <code className="ml-1 truncate rounded bg-muted/50 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
          {run_id}
        </code>
      </div>
      <div className="p-3 space-y-2">
        {loading && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading…
          </div>
        )}
        {!loading && !data && (
          <p className="text-xs text-muted-foreground">No data for this run.</p>
        )}
        {!loading && data && (
          <>
            <div className="flex items-center gap-3">
              {passRate != null && (
                <div className="flex items-center gap-1.5">
                  {passed ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span className="text-sm font-semibold text-foreground/90">
                    {(passRate * 100).toFixed(0)}% pass
                  </span>
                </div>
              )}
              {(data.agent_name || data.agent) && (
                <span className="text-[11px] text-muted-foreground">
                  agent:{" "}
                  <span className="text-foreground/80">{data.agent_name ?? data.agent}</span>
                </span>
              )}
              {(data.duration_seconds ?? data.duration) != null && (
                <span className="text-[11px] text-muted-foreground">
                  {(data.duration_seconds ?? data.duration ?? 0).toFixed(1)}s
                </span>
              )}
            </div>
            {(data.precision != null || data.recall != null || data.f1 != null) && (
              <div className="grid grid-cols-3 gap-2 text-[10px]">
                <Metric label="Precision" value={data.precision} />
                <Metric label="Recall" value={data.recall} />
                <Metric label="F1" value={data.f1} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
