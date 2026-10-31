"use client";

import { useEffect, useState } from "react";
import { Activity, EyeOff, TimerReset } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

const DISCLOSURES = [
  { icon: Activity, title: "What may be recorded", detail: "Service logs, timing data, tool and agent activity, and model-usage counts. This version does not guarantee that conversation text or personal data is excluded from logs or traces." },
  { icon: EyeOff, title: "Before data is kept", detail: "Server rules can keep only a sample of activity and hide configured fields." },
  { icon: TimerReset, title: "How long data is kept", detail: "The person who runs this Companion X deployment chooses how long raw data and daily summaries are kept." },
] as const;

interface Status {
  collecting: boolean; sampleRate: number; redactedFieldNames: string[];
  rawRetentionDays: number; rollupRetentionDays: number; configurable: boolean;
}

function statusFrom(raw: unknown): Status {
  const v = unwrapToolData(raw) as Record<string, unknown>;
  if (typeof v.collecting !== "boolean") throw new Error("Collection status unavailable.");
  const names = Array.isArray(v.redacted_field_names) ? v.redacted_field_names.filter((n): n is string => typeof n === "string") : [];
  return {
    collecting: v.collecting, sampleRate: typeof v.sample_rate === "number" ? v.sample_rate : 1,
    redactedFieldNames: names, rawRetentionDays: typeof v.raw_retention_days === "number" ? v.raw_retention_days : 7,
    rollupRetentionDays: typeof v.rollup_retention_days === "number" ? v.rollup_retention_days : 365,
    configurable: v.configurable === true,
  };
}

/** Settings → Privacy. Live status keeps the disclosure text honest: it must
 * match what telemetry_get_collection_status actually reports, not a claim. */
export default function PrivacySettingsPanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    callTool("telemetry_get_collection_status").then((raw) => setStatus(statusFrom(raw))).catch(() => setError("Collection status unavailable."));
  }, []);

  return <section aria-labelledby="privacy-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="privacy-settings-title" className="text-sm font-semibold">Privacy</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">This version records technical activity so the people running it can monitor reliability.</p>
    {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
    {status && <div className="mt-4 rounded-md border border-border/40 p-4">
      <p className="text-[10px] font-medium uppercase tracking-wider text-violet-300">Current collection</p>
      <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
        <Row label="Sample rate" value={`${Math.round(status.sampleRate * 100)}%`} />
        <Row label="Hidden fields" value={status.redactedFieldNames.length ? status.redactedFieldNames.join(", ") : "none"} />
        <Row label="Raw data kept" value={`${status.rawRetentionDays} days`} />
        <Row label="Summaries kept" value={`${status.rollupRetentionDays} days`} />
      </dl>
      <p className="mt-3 text-[11px] text-muted-foreground">{status.configurable
        ? "The operator sets these via environment variables before starting the deployment."
        : "These values are fixed by the deployment; no operator lever exists yet."}</p>
    </div>}
    <div className="mt-4 grid gap-3 sm:grid-cols-3">{DISCLOSURES.map((item) => <article key={item.title} className="rounded-md border border-border/40 p-4">
      <item.icon className="h-5 w-5 text-violet-400" /><h3 className="mt-3 text-sm font-medium">{item.title}</h3>
      <p className="mt-1 text-xs text-muted-foreground">{item.detail}</p>
    </article>)}</div>
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">You cannot turn this collection off for only your account. The people running this Companion X deployment control what is collected, where it is sent, what fields are hidden, and how long it is kept.</p>
  </section>;
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md border border-border/30 px-3 py-2">
    <dt className="text-[10px] text-muted-foreground">{label}</dt>
    <dd className="m-0 truncate font-mono text-[11px] text-foreground/90" title={value}>{value}</dd>
  </div>;
}
