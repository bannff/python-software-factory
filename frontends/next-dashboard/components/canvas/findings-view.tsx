"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFindings } from "@/lib/hooks/use-findings";
import { ComponentTree } from "@companion-x/shared-renderer";
import { FindingDetail } from "./finding-detail";
import {
  usePaintedComponents,
  type CanvasState,
} from "@/lib/copilotkit/a2ui-canvas-slots";
import {
  SEV_ORDER,
  SEV_PILL_COLORS,
  SEV_BAR_COLORS,
  SEV_CARD_BG,
  SEV_CARD_GLOW,
  STRIDE_COLORS,
  arnFragment,
} from "./findings-view-style";
import type { Step, FindingSeverity, ActiveToolCall } from "@/lib/types";

interface FindingsViewProps {
  steps: Step[];
  toolCalls: ActiveToolCall[];
  agentState: { canvas?: CanvasState } & Record<string, unknown>;
}

export default function FindingsView({ toolCalls, agentState }: FindingsViewProps) {
  const findings = useFindings(toolCalls);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterSev, setFilterSev] = useState<FindingSeverity | "all">("all");

  /* Carrier #2: when the agent paints `state.canvas.findings` with an
   * A2UI components tree, render that tree directly (lossless A2UI
   * render). Empty slot falls back to today's MCP-loaded findings list. */
  const findingsSlot = useMemo(
    () => agentState.canvas?.findings,
    [agentState.canvas?.findings],
  );
  const paintedComponents = usePaintedComponents(findingsSlot);
  if (paintedComponents.length > 0) {
    return (
      <div className="flex h-full flex-col" style={{ minHeight: 0 }}>
        <div className="flex items-center gap-2 border-b border-border/50 bg-card/10 px-4 py-2">
          <span className="text-xs font-medium text-muted-foreground">
            {findingsSlot?.name ?? "Findings"} · agent-painted
          </span>
        </div>
        <div className="flex-1 overflow-auto p-4">
          <ComponentTree nodes={paintedComponents} />
        </div>
      </div>
    );
  }

  const counts = SEV_ORDER.reduce((acc, s) => {
    acc[s] = findings.filter((f) => f.severity === s).length;
    return acc;
  }, {} as Record<string, number>);

  const total = findings.length || 1; // avoid div/0

  const filtered = filterSev === "all" ? findings : findings.filter((f) => f.severity === filterSev);
  const sorted = [...filtered].sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));

  return (
    <div className="flex h-full flex-col">
      {/* Header: stacked bar + filter pills */}
      <div className="border-b border-border/50 bg-card/10 px-4 py-2 space-y-2">
        {/* Row 1: severity distribution bar */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-muted-foreground shrink-0 mr-1">{findings.length}</span>
          <div className="flex flex-1 h-5 rounded-md overflow-hidden gap-px">
            {SEV_ORDER.map((sev, i) => {
              const pct = (counts[sev] / total) * 100;
              if (counts[sev] === 0) return null;
              return (
                <motion.button
                  key={sev}
                  title={`${counts[sev]} ${sev}`}
                  onClick={() => setFilterSev(filterSev === sev ? "all" : sev)}
                  className={cn(
                    "relative flex items-center justify-center text-[9px] font-semibold text-white/90 transition-opacity hover:opacity-80",
                    SEV_BAR_COLORS[sev],
                    filterSev !== "all" && filterSev !== sev && "opacity-40",
                  )}
                  style={{ width: `${pct}%`, minWidth: 4 }}
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 0.5, delay: i * 0.07, ease: "easeOut" }}
                >
                  {pct > 8 && <span className="truncate px-1">{counts[sev]}</span>}
                </motion.button>
              );
            })}
          </div>
        </div>

        {/* Row 2: filter pills — only show severities with findings */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {SEV_ORDER.filter((sev) => counts[sev] > 0).map((sev) => (
            <button
              key={sev}
              onClick={() => setFilterSev(filterSev === sev ? "all" : sev)}
              className={cn(
                "rounded-full px-2 py-0.5 text-[9px] font-medium transition-colors",
                filterSev === sev ? "ring-1 ring-ring/50" : "",
                SEV_PILL_COLORS[sev],
              )}
            >
              {counts[sev]} {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Findings list */}
      <div className="flex-1 overflow-auto p-4">
        {sorted.length > 0 ? (
          <div className="space-y-2">
            {sorted.map((finding) => {
              const hasGlow = finding.severity === "critical" || finding.severity === "high";
              return (
                <div key={finding.id}>
                  <motion.button
                    onClick={() => setExpandedId(expandedId === finding.id ? null : finding.id)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg border border-border/50 px-3 py-2.5 text-left hover:bg-accent/20 transition-colors",
                      "bg-card/30",
                      SEV_CARD_BG[finding.severity] ?? "",
                    )}
                    style={hasGlow ? SEV_CARD_GLOW[finding.severity] : undefined}
                    animate={hasGlow ? {
                      boxShadow: [
                        SEV_CARD_GLOW[finding.severity].boxShadow as string,
                        SEV_CARD_GLOW[finding.severity].boxShadow?.toString().replace("0.15", "0.25").replace("0.1", "0.18") ?? "",
                        SEV_CARD_GLOW[finding.severity].boxShadow as string,
                      ],
                    } : undefined}
                    transition={hasGlow ? { duration: 3, repeat: Infinity, ease: "easeInOut" } : undefined}
                  >
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium shrink-0", SEV_PILL_COLORS[finding.severity])}>
                      {finding.severity}
                    </span>
                    {finding.cwe && (
                      <span className="font-mono text-[9px] bg-muted/40 rounded px-1 text-muted-foreground shrink-0">{finding.cwe}</span>
                    )}
                    <span className="flex-1 text-sm font-medium truncate">{finding.title}</span>
                    {finding.category && (
                      <span className={cn("rounded-full px-1.5 py-0.5 text-[9px] font-medium shrink-0", STRIDE_COLORS[finding.category] ?? "bg-muted/40 text-muted-foreground")}>
                        {finding.category}
                      </span>
                    )}
                    {finding.affected_resource_arn && (
                      <span className="text-[9px] text-muted-foreground/60 font-mono truncate max-w-[140px] shrink-0">
                        {arnFragment(finding.affected_resource_arn)}
                      </span>
                    )}
                    <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", finding.source === "live" ? "bg-violet-400 animate-pulse" : "bg-blue-400/60")} title={finding.source === "live" ? "live session" : "graph"} />
                    <ChevronRight className={cn("h-3.5 w-3.5 text-muted-foreground transition-transform shrink-0", expandedId === finding.id && "rotate-90")} />
                  </motion.button>
                  <AnimatePresence>
                    {expandedId === finding.id && <FindingDetail finding={finding} />}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyFindings />
        )}
      </div>
    </div>
  );
}

function EmptyFindings() {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10">
        <Shield className="h-6 w-6 text-emerald-500/50" />
      </div>
      <p className="text-sm text-muted-foreground">No findings yet. Run a security scan to see results here.</p>
    </motion.div>
  );
}
