"use client";

import { useMemo, useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import type { Finding, FindingSeverity, ActiveToolCall } from "@/lib/types";

/** Any tool may report findings; only the security brick returns a bare list. */
function findingItems(name: string, result: unknown): unknown[] {
  const r = result as { findings?: unknown; issues?: unknown } | unknown[] | null;
  if (Array.isArray(r)) return /^security_/.test(name) ? r : [];
  const items = r?.findings ?? r?.issues;
  return Array.isArray(items) ? items : [];
}

function parseSeverity(raw: unknown): FindingSeverity {
  const s = String(raw).toLowerCase();
  if (s === "critical" || s === "high" || s === "medium" || s === "low") return s;
  return "info";
}

function parseFindings(items: unknown[], sourceId: string, sourceName: string): Finding[] {
  const findings: Finding[] = [];
  const arr = Array.isArray(items) ? items : [];
  for (const item of arr) {
    const f = item as Record<string, unknown>;
    findings.push({
      id: `${sourceId}-${findings.length}`,
      severity: parseSeverity(f.severity ?? f.level),
      title: (f.title ?? f.name ?? f.message ?? "Finding") as string,
      resource: (f.resource ?? f.target ?? f.location ?? sourceName) as string,
      type: (f.type ?? f.category ?? "other") as string,
      description: (f.description ?? f.detail ?? "") as string,
      evidence: (f.evidence ?? f.snippet ?? undefined) as string | undefined,
      remediation: (f.remediation ?? f.fix ?? undefined) as string | undefined,
      cwe: f.cwe ? String(f.cwe) : undefined,
      category: f.category ? String(f.category) : undefined,
      affected_resource_arn: f.affected_resource_arn ? String(f.affected_resource_arn) : undefined,
      timestamp: Date.now(),
      source: "live" as const,
    });
  }
  return findings;
}

/** Unwrap the typed graph_get_recent_findings envelope to a flat row list. */
function unwrapTypedRows(raw: unknown): Record<string, unknown>[] {
  const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
  const result = (parsed as Record<string, unknown>)?.result ?? parsed;
  const rows = (result as Record<string, unknown>)?.rows;
  return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : [];
}

const str = (v: unknown): string | undefined => (v === undefined || v === null || v === "" ? undefined : String(v));

function taxonomyFrom(raw: unknown): Finding["taxonomy"] {
  if (!Array.isArray(raw)) return undefined;
  const items = raw.flatMap((t) => {
    const x = t as Record<string, unknown>;
    return typeof x?.scheme === "string" && typeof x?.id === "string"
      ? [{ scheme: x.scheme, id: x.id, label: typeof x.label === "string" ? x.label : "" }] : [];
  });
  return items.length > 0 ? items : undefined;
}

/** Prefers the neutral `row.finding` shape; falls back to the legacy flat columns. */
function rowToFinding(r: Record<string, unknown>, idx: number): Finding {
  const n = (r.finding ?? {}) as Record<string, unknown>;
  const subject = (n.subject ?? {}) as Record<string, unknown>;
  const arn = str(r.affected_resource_arn);
  const kind = str(n.kind) ?? str(r.finding_type) ?? "other";
  return {
    id: str(n.id) ?? str(r.id) ?? `graph-finding-${idx}`,
    severity: parseSeverity(n.severity ?? r.severity),
    title: (str(n.title) ?? str(r.title) ?? "Finding").slice(0, 80),
    resource: arn ?? str(subject.id) ?? str(subject.location) ?? "unknown",
    affected_resource_arn: arn,
    type: kind,
    kind,
    state: str(n.state) ?? str(r.state),
    description: str(n.description) ?? str(r.description) ?? "",
    evidence: str(n.evidence) ?? str(r.evidence),
    cwe: str(r.cwe) ?? str(r.cwe_id),
    category: str(n.category) ?? str(r.category),
    remediation: str(n.remediation) ?? str(r.remediation),
    taxonomy: taxonomyFrom(n.taxonomy),
    run_id: str(r.run_id) ?? str((n.source as Record<string, unknown> | undefined)?.run_id),
    timestamp: Date.now(),
    source: "graph" as const,
  };
}

/**
 * Extract findings (security or otherwise) from:
 * 1. Completed tool call results in the chat (reactive)
 * 2. The graph brick's typed graph_get_recent_findings tool (on mount).
 *    Rows are flat dicts with CWE/OCSF taxonomy already joined.
 */
export const FINDINGS_CHANGED = "companion-x:findings-changed";

/** Tell every open Findings view to reload after a finding is recorded or its state changes. */
export function notifyFindingsChanged(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(FINDINGS_CHANGED));
}

export function useFindings(toolCalls: ActiveToolCall[]): Finding[] {
  const [mcpFindings, setMcpFindings] = useState<Finding[]>([]);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener(FINDINGS_CHANGED, bump);
    return () => window.removeEventListener(FINDINGS_CHANGED, bump);
  }, []);

  useEffect(() => {
    callTool("graph_get_recent_findings", {
      severity: "", app: "", run_id: "", limit: 50,
    })
      .then((raw) => {
        const rows = unwrapTypedRows(raw);
        setMcpFindings(rows.map(rowToFinding));
      })
      .catch(() => { /* no-op — graph may not be available */ });
  }, [version]);

  // Parse findings from chat tool call results
  const chatFindings = useMemo(() => {
    const findings: Finding[] = [];
    for (const tc of toolCalls) {
      if (tc.active || !tc.result || !tc.name) continue;

      try {
        const result = typeof tc.result === "string" ? JSON.parse(tc.result) : tc.result;
        findings.push(...parseFindings(findingItems(tc.name, result), tc.id, tc.name));
      } catch {
        // Non-JSON result — skip
      }
    }
    return findings;
  }, [toolCalls]);

  // Merge MCP findings + chat findings, dedup by id
  return useMemo(() => {
    const seen = new Set<string>();
    const merged: Finding[] = [];
    for (const f of [...mcpFindings, ...chatFindings]) {
      if (!seen.has(f.id)) {
        seen.add(f.id);
        merged.push(f);
      }
    }
    return merged;
  }, [mcpFindings, chatFindings]);
}
