"use client";

/**
 * <FindingCard /> — agent-summonable single-finding summary
 * (bd-kzsl Phase 1, component 2/3).
 *
 * Pulls from `graph_get_recent_findings` (the typed CWE/OCSF row
 * source used by the Findings view) and matches by id; if the id
 * isn't on the recent list, falls back to the first available row so
 * the card stays useful in low-cardinality dev environments.
 */

import { useEffect, useState } from "react";
import { ChevronRight, ShieldAlert } from "lucide-react";
import { z } from "zod";
import { callTool } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SEVERITY_COLOR } from "./_shared";

export const FindingArgs = z.object({
  finding_id: z.string().describe("The finding id to display."),
  cwe: z.string().optional().describe("Optional CWE id, e.g. CWE-79."),
  severity: z
    .string()
    .optional()
    .describe("Optional severity (critical|high|medium|low|info)."),
});

interface FindingData {
  title?: string;
  description?: string;
  severity?: string;
  cwe?: string;
  affected_resource_arn?: string;
  resource?: string;
  confidence?: number | string;
}

function unwrapRows(raw: unknown): Record<string, unknown>[] {
  const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
  if (parsed && typeof parsed === "object") {
    const r = (parsed as { result?: unknown }).result ?? parsed;
    if (Array.isArray(r)) return r as Record<string, unknown>[];
    if (r && typeof r === "object") {
      const rows = (r as { rows?: unknown }).rows;
      if (Array.isArray(rows)) return rows as Record<string, unknown>[];
    }
  }
  return [];
}

export function FindingCard({ finding_id, cwe, severity }: z.infer<typeof FindingArgs>) {
  const [data, setData] = useState<FindingData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await callTool("graph_get_recent_findings", { limit: 50 });
        if (cancelled) return;
        const rows = unwrapRows(raw);
        const match = rows.find((r) => String(r.id ?? "") === finding_id) ?? rows[0] ?? null;
        setData(
          match
            ? {
                title: String(match.title ?? "Finding"),
                description: String(match.description ?? ""),
                severity: String(match.severity ?? severity ?? "info").toLowerCase(),
                cwe: cwe ?? (match.cwe ? String(match.cwe) : undefined),
                affected_resource_arn: match.affected_resource_arn
                  ? String(match.affected_resource_arn)
                  : undefined,
                resource: match.resource ? String(match.resource) : undefined,
                confidence: match.confidence as number | string | undefined,
              }
            : null,
        );
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "fetch failed");
      }
    })();
    return () => { cancelled = true; };
  }, [finding_id, cwe, severity]);

  const sev = (data?.severity ?? severity ?? "info").toLowerCase();
  const sevClass = SEVERITY_COLOR[sev] ?? SEVERITY_COLOR.info;
  const cweId = data?.cwe ?? cwe;

  return (
    <div className="ml-11 my-2 rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm overflow-hidden shadow-sm">
      <div className="flex items-start gap-2 p-3">
        <ShieldAlert className="h-4 w-4 mt-0.5 shrink-0 text-amber-500" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase", sevClass)}>
              {sev}
            </span>
            {cweId && (
              <a
                href={`https://cwe.mitre.org/data/definitions/${cweId.replace(/^CWE-?/i, "")}.html`}
                target="_blank"
                rel="noreferrer"
                className="rounded bg-blue-500/15 px-1.5 py-0.5 text-[10px] font-medium text-blue-500 hover:underline"
              >
                {cweId}
              </a>
            )}
            <code className="truncate rounded bg-muted/50 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
              {finding_id}
            </code>
          </div>
          <div className="text-xs font-medium text-foreground/90 truncate">
            {data?.title ?? (error ? "Finding (lookup failed)" : "Finding")}
          </div>
          {(data?.affected_resource_arn || data?.resource) && (
            <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <ChevronRight className="h-3 w-3" />
              <span className="truncate font-mono">
                {data?.affected_resource_arn ?? data?.resource}
              </span>
            </div>
          )}
          {data?.description && (
            <p className="text-[11px] text-muted-foreground/90 line-clamp-3">
              {data.description}
            </p>
          )}
          {data?.confidence != null && (
            <div className="text-[10px] text-muted-foreground">
              Confidence: <span className="font-medium text-foreground/80">{String(data.confidence)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
