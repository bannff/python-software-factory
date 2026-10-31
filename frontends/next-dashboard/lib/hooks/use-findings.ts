"use client";

import { useMemo, useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import type { Finding, FindingSeverity, ActiveToolCall } from "@/lib/types";

const SECURITY_PATTERNS = [
  /^security_/,
  /posture/i,
  /threat/i,
  /vulnerability/i,
  /scan/i,
];

function isSecurityTool(name: string): boolean {
  return SECURITY_PATTERNS.some((p) => p.test(name));
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
      type: (f.type ?? f.category ?? "vulnerability") as string,
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

function rowToFinding(r: Record<string, unknown>, idx: number): Finding {
  const arn = r.affected_resource_arn ? String(r.affected_resource_arn) : undefined;
  const cwe = r.cwe ? String(r.cwe) : r.cwe_id ? String(r.cwe_id) : undefined;
  return {
    id: (r.id as string) ?? `graph-finding-${idx}`,
    severity: parseSeverity(r.severity),
    title: r.title ? String(r.title).slice(0, 80) : "Finding",
    resource: arn ?? "unknown",
    affected_resource_arn: arn,
    type: r.finding_type ? String(r.finding_type) : "vulnerability",
    description: (r.description ?? "") as string,
    cwe,
    category: r.category ? String(r.category) : undefined,
    remediation: r.remediation ? String(r.remediation) : undefined,
    timestamp: Date.now(),
    source: "graph" as const,
  };
}

/**
 * Extract security findings from:
 * 1. Completed tool call results in the chat (reactive)
 * 2. The graph brick's typed graph_get_recent_findings tool (on mount).
 *    Rows are flat dicts with CWE/OCSF taxonomy already joined.
 */
export function useFindings(toolCalls: ActiveToolCall[]): Finding[] {
  const [mcpFindings, setMcpFindings] = useState<Finding[]>([]);

  useEffect(() => {
    callTool("graph_get_recent_findings", {
      severity: "", app: "", run_id: "", limit: 50,
    })
      .then((raw) => {
        const rows = unwrapTypedRows(raw);
        setMcpFindings(rows.map(rowToFinding));
      })
      .catch(() => { /* no-op — graph may not be available */ });
  }, []);

  // Parse findings from chat tool call results
  const chatFindings = useMemo(() => {
    const findings: Finding[] = [];
    for (const tc of toolCalls) {
      if (tc.active || !tc.result || !tc.name) continue;
      if (!isSecurityTool(tc.name)) continue;

      try {
        const result = typeof tc.result === "string" ? JSON.parse(tc.result) : tc.result;
        const items = result?.findings ?? result?.issues ?? (Array.isArray(result) ? result : []);
        findings.push(...parseFindings(items, tc.id, tc.name));
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
