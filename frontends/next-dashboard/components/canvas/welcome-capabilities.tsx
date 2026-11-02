"use client";

import {
  ListChecks, Network, GitBranch, Beaker, BarChart3,
  Brain, Gamepad2, Link2, Container, type LucideIcon,
} from "lucide-react";
import type { CanvasViewId } from "@/lib/types";

export const CAPABILITIES: { icon: LucideIcon; label: string; desc: string; viewId: CanvasViewId }[] = [
  { icon: ListChecks, label: "Findings",   desc: "Issues found by any analysis, ranked by severity", viewId: "findings" },
  { icon: Beaker,    label: "Evals",      desc: "Benchmark agents with LLMAJ rubric scoring", viewId: "evals" },
  { icon: BarChart3, label: "Metrics",    desc: "Watch live runtime telemetry from the current buffer", viewId: "metrics" },
  { icon: Network,   label: "Graph",      desc: "Explore knowledge graphs and entity relationships", viewId: "graph" },
  { icon: GitBranch, label: "Timeline",   desc: "Watch agent tool calls live", viewId: "timeline-v2" },
  { icon: Brain,     label: "ML",         desc: "Fine-tuning pipelines and dataset generation", viewId: "ml" },
  { icon: Gamepad2,  label: "Games",      desc: "RL game arena — CTF challenges", viewId: "games" },
  { icon: Link2,     label: "Blockchain", desc: "Token economy — wallets and bounties", viewId: "blockchain" },
  { icon: Container, label: "Sandbox",    desc: "Docker containers for agent execution", viewId: "sandbox" },
];

/** One bordered table of rows: icon, name, description. */
export function CapabilityTable({ onNavigate }: { onNavigate?: (viewId: CanvasViewId) => void }) {
  return (
    <div className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-border/30 bg-border/20">
      {CAPABILITIES.map(({ icon: Icon, label, desc, viewId }) => (
        <button key={viewId} type="button" onClick={() => onNavigate?.(viewId)}
          className="group flex items-center gap-3 bg-card/40 px-4 py-2.5 text-left transition-colors hover:bg-accent/30">
          <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-foreground/70" aria-hidden />
          <span className="w-20 shrink-0 text-[12px] font-medium text-foreground/70">{label}</span>
          <span className="text-[11px] text-muted-foreground/40 transition-colors group-hover:text-muted-foreground/60">{desc}</span>
        </button>
      ))}
    </div>
  );
}
