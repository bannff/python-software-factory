"use client";

import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ListChecks, Play } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";
import { useFindings } from "@/lib/hooks/use-findings";
import { ComponentTree } from "@companion-x/shared-renderer";
import { FindingDetail } from "./finding-detail";
import { FindingRow } from "./finding-row";
import { kindCounts } from "./finding-kinds";
import {
  usePaintedComponents,
  type CanvasState,
} from "@/lib/copilotkit/a2ui-canvas-slots";
import {
  SEV_ORDER,
  SEV_PILL_COLORS,
  SEV_BAR_COLORS,
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
  const [filterKind, setFilterKind] = useState<string | null>(null);

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

  const kinds = kindCounts(findings);
  const filtered = findings.filter((f) =>
    (filterSev === "all" || f.severity === filterSev) && (filterKind === null || f.type === filterKind));
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

        {/* Row 3: kind chips — only when more than one kind is present */}
        {kinds.length > 1 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {kinds.map(([kind, n]) => (
              <button key={kind} type="button" aria-pressed={filterKind === kind}
                onClick={() => setFilterKind(filterKind === kind ? null : kind)}
                className={cn("rounded-full border border-border/50 px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-accent/30",
                  filterKind === kind && "bg-accent/40 text-foreground")}>
                {kind} {n}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Findings list */}
      <div className="flex-1 overflow-auto p-4">
        {sorted.length > 0 ? (
          <div className="space-y-2">
            {sorted.map((finding) => (
              <div key={finding.id}>
                <FindingRow finding={finding} expanded={expandedId === finding.id}
                  onToggle={() => setExpandedId(expandedId === finding.id ? null : finding.id)} />
                <AnimatePresence>
                  {expandedId === finding.id && <FindingDetail finding={finding} />}
                </AnimatePresence>
              </div>
            ))}
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
    <EmptyState icon={ListChecks} title="No findings yet"
      action={{ icon: Play, label: "Run an analysis", prompt: "Analyze the system and report any findings" }} />
  );
}
