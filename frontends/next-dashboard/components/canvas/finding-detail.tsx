"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check, Shield, ExternalLink } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/utils";
import type { Finding } from "@/lib/types";

interface FindingDetailProps {
  finding: Finding;
}

const SEV_COLORS: Record<string, string> = {
  critical: "border-red-500/30 bg-red-500/5",
  high:     "border-orange-500/30 bg-orange-500/5",
  medium:   "border-yellow-500/30 bg-yellow-500/5",
  low:      "border-blue-500/30 bg-blue-500/5",
  info:     "border-gray-500/30 bg-gray-500/5",
};

const STRIDE_COLORS: Record<string, string> = {
  "Elevation of Privilege": "bg-red-500/10 text-red-400",
  "Information Disclosure":  "bg-yellow-500/10 text-yellow-400",
  "Denial of Service":       "bg-orange-500/10 text-orange-400",
  "Tampering":               "bg-orange-500/10 text-orange-400",
  "Spoofing":                "bg-gray-500/10 text-gray-400",
  "Repudiation":             "bg-purple-500/10 text-purple-400",
};

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <button onClick={copy} className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors">
      {copied ? <Check className="h-2.5 w-2.5 text-emerald-400" /> : <Copy className="h-2.5 w-2.5" />}
      {copied ? "Copied" : label}
    </button>
  );
}

function CweLink({ cwe }: { cwe: string }) {
  const num = cwe.replace(/^CWE-/i, "");
  return (
    <a href={`https://cwe.mitre.org/data/definitions/${num}.html`} target="_blank" rel="noopener noreferrer"
      className="flex items-center gap-0.5 font-mono text-[10px] bg-muted/40 rounded px-1 text-blue-400 hover:text-blue-300 transition-colors">
      {cwe}<ExternalLink className="h-2 w-2" />
    </a>
  );
}

export function FindingDetail({ finding }: FindingDetailProps) {
  const copyMarkdown = () => {
    const md = [
      `## ${finding.title}`,
      `**Severity:** ${finding.severity}`,
      finding.cwe ? `**CWE:** ${finding.cwe}` : "",
      finding.category ? `**Category:** ${finding.category}` : "",
      finding.affected_resource_arn ? `**ARN:** ${finding.affected_resource_arn}` : "",
      finding.analysis_id ? `**Analysis:** ${finding.analysis_id}` : "",
      "",
      finding.description,
      finding.evidence ? `\n### Evidence\n\`\`\`\n${finding.evidence}\n\`\`\`` : "",
      finding.remediation ? `\n### Remediation\n${finding.remediation}` : "",
    ].filter(Boolean).join("\n");
    navigator.clipboard.writeText(md);
  };

  return (
    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
      <div className={cn("rounded-lg border p-3 mt-2 space-y-3", SEV_COLORS[finding.severity] ?? SEV_COLORS.info)}>

        {/* Action bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-[10px] font-medium text-muted-foreground">{finding.type}</span>
          </div>
          <div className="flex items-center gap-1">
            {finding.affected_resource_arn && <CopyButton value={finding.affected_resource_arn} label="Copy ARN" />}
            <CopyButton value={(() => {
              const md = [`## ${finding.title}`, `**Severity:** ${finding.severity}`, finding.cwe ? `**CWE:** ${finding.cwe}` : "", finding.affected_resource_arn ? `**ARN:** ${finding.affected_resource_arn}` : "", "", finding.description, finding.remediation ? `\n### Remediation\n${finding.remediation}` : ""].filter(Boolean).join("\n");
              return md;
            })()} label="Copy MD" />
          </div>
        </div>

        {/* Two-zone metadata */}
        <div className="flex gap-3 text-[11px] border-t border-border/20 pt-2">
          {/* Config zone */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 min-w-0">
            {finding.cwe && (
              <span className="flex items-center gap-1"><span className="text-muted-foreground/50">CWE:</span><CweLink cwe={finding.cwe} /></span>
            )}
            {finding.category && (
              <span className="flex items-center gap-1">
                <span className="text-muted-foreground/50">Category:</span>
                <span className={cn("rounded-full px-1.5 py-0.5 text-[9px] font-medium", STRIDE_COLORS[finding.category] ?? "bg-muted/40 text-muted-foreground")}>{finding.category}</span>
              </span>
            )}
            {finding.type && <span className="flex items-center gap-1"><span className="text-muted-foreground/50">Type:</span><span className="text-foreground/70">{finding.type}</span></span>}
          </div>
          {/* Identity zone */}
          <div className="flex flex-wrap gap-x-3 gap-y-1 shrink-0 pl-3 border-l border-border/20">
            <span className="flex items-center gap-1 group">
              <span className="text-muted-foreground/50">ID:</span>
              <span className="font-mono text-foreground/70 text-[10px]">{finding.id.slice(0, 16)}</span>
            </span>
            {finding.affected_resource_arn && (
              <span className="flex items-center gap-1">
                <span className="text-muted-foreground/50">ARN:</span>
                <span className="font-mono text-foreground/70 text-[10px] truncate max-w-[160px]">{finding.affected_resource_arn.split(":").slice(-2).join("/").slice(0, 40)}</span>
              </span>
            )}
          </div>
        </div>

        {/* Description */}
        {finding.description && <p className="text-sm text-foreground/80">{finding.description}</p>}

        {/* Evidence */}
        {finding.evidence && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">Evidence</p>
            <SyntaxHighlighter style={oneDark} language="text" PreTag="div" className="!rounded-lg !text-xs !p-3 !m-0 max-h-32 overflow-auto">
              {finding.evidence}
            </SyntaxHighlighter>
          </div>
        )}

        {/* Remediation */}
        {finding.remediation && (
          <div className="rounded bg-emerald-500/5 border border-emerald-500/20 px-2 py-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400/70 mb-0.5">Remediation</p>
            <p className="text-xs text-foreground/70">{finding.remediation}</p>
          </div>
        )}

        {/* Analysis lineage breadcrumb */}
        {finding.analysis_id && (
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/60 border-t border-border/20 pt-2">
            <span className="font-mono bg-muted/30 rounded px-1">{finding.id.slice(0, 16)}</span>
            <span>←</span>
            <span className="font-mono bg-muted/30 rounded px-1">{finding.analysis_id.slice(0, 20)}</span>
            {finding.analysis_target && (
              <>
                <span>←</span>
                <span className="text-foreground/50 truncate max-w-[120px]">{finding.analysis_target}</span>
              </>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
