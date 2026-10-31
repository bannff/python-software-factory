"use client";

import { useEffect, useState } from "react";
import { Coins, MessageSquareText, Timer, Wrench, AlertTriangle } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Row 52 (Usage): upstream shows token/turn usage over a calendar date
 * range. Companion-X's telemetry brick tracks real cumulative counters
 * (`get_metrics_summary`) but has no persisted, bucketed time-series —
 * they reset on process restart. Rather than fabricate a history that
 * doesn't exist, this panel shows the real running totals since the
 * gateway's current process started, labeled honestly as such. A true
 * calendar-range history is real, separate work (persisted rollups) —
 * disclosed, not silently faked.
 */
interface Snapshot {
  started_at: number;
  llm: { interactions: number; input_tokens: number; output_tokens: number; total_tokens: number; cost_usd: number; last_latency_ms: number | null };
  agent: { executions: number };
  tools: { invocations: number };
  errors: number;
}

function useMetricsSnapshot() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const res = await callTool("get_metrics_summary", {});
        if (!mounted) return;
        setData(unwrapToolData(res) as unknown as Snapshot);
        setError(null);
      } catch {
        if (!mounted) return;
        setError("Usage metrics are unavailable right now.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  return { data, error, loading };
}

export default function UsageSettingsPanel() {
  const { data, error, loading } = useMetricsSnapshot();

  if (loading) return <Shell><p className="text-xs text-muted-foreground">Loading usage…</p></Shell>;
  if (error || !data) return <Shell>
    <p role="alert" className="flex items-center gap-2 text-xs text-amber-300">
      <AlertTriangle className="h-4 w-4 shrink-0" />{error ?? "Usage metrics are unavailable right now."}
    </p>
  </Shell>;

  const since = new Date(data.started_at * 1000).toLocaleString();
  const items = [
    { icon: MessageSquareText, label: "LLM turns", value: data.llm.interactions.toLocaleString() },
    { icon: Coins, label: "Tokens (in / out)", value: `${data.llm.input_tokens.toLocaleString()} / ${data.llm.output_tokens.toLocaleString()}` },
    { icon: Coins, label: "Estimated cost", value: `$${data.llm.cost_usd.toFixed(4)}` },
    { icon: Wrench, label: "Tool invocations", value: data.tools.invocations.toLocaleString() },
    { icon: Timer, label: "Last turn latency", value: data.llm.last_latency_ms != null ? `${Math.round(data.llm.last_latency_ms)} ms` : "—" },
    { icon: AlertTriangle, label: "Errors", value: data.errors.toLocaleString() },
  ];

  return <Shell>
    <dl className="grid gap-3 sm:grid-cols-2">
      {items.map((item) => <div key={item.label} className="flex items-center gap-3 rounded-md border border-border/40 p-4">
        <item.icon className="h-5 w-5 shrink-0 text-violet-400" />
        <div><dt className="text-[10px] uppercase tracking-wider text-muted-foreground">{item.label}</dt>
          <dd className="mt-1 text-sm font-medium">{item.value}</dd></div>
      </div>)}
    </dl>
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">
      Running totals since the gateway process started ({since}), not a calendar-range history —
      Companion X does not yet persist usage into day-by-day buckets, so a date-range picker isn&apos;t offered here.
    </p>
  </Shell>;
}

function Shell({ children }: { children: React.ReactNode }) {
  return <section aria-labelledby="usage-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="usage-settings-title" className="text-sm font-semibold">Usage</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Token, cost, and activity counters for this running gateway.</p>
    <div className="mt-4">{children}</div>
  </section>;
}
