"use client";

import {
  Shield, Network, GitBranch, Beaker, BarChart3,
  Brain, Gamepad2, Link2, Container, type LucideIcon,
} from "lucide-react";
import type { CanvasViewId } from "@/lib/types";

export const CAPABILITIES: { icon: LucideIcon; label: string; desc: string; viewId: CanvasViewId }[] = [
  { icon: Shield,    label: "Findings",   desc: "Security findings with severity and STRIDE classification", viewId: "findings" },
  { icon: Beaker,    label: "Evals",      desc: "Benchmark agents with LLMAJ rubric scoring", viewId: "evals" },
  { icon: BarChart3, label: "Metrics",    desc: "Watch live runtime telemetry from the current buffer", viewId: "metrics" },
  { icon: Network,   label: "Graph",      desc: "Explore knowledge graphs and entity relationships", viewId: "graph" },
  { icon: GitBranch, label: "Timeline",   desc: "Watch agent tool calls live", viewId: "timeline-v2" },
  { icon: Brain,     label: "ML",         desc: "Fine-tuning pipelines and dataset generation", viewId: "ml" },
  { icon: Gamepad2,  label: "Games",      desc: "RL game arena — CTF challenges", viewId: "games" },
  { icon: Link2,     label: "Blockchain", desc: "Token economy — wallets and bounties", viewId: "blockchain" },
  { icon: Container, label: "Sandbox",    desc: "Docker containers for agent execution", viewId: "sandbox" },
];

/** Metrics-pane style: icon cards, label only; the description is a tooltip. */
export function CapabilityGrid({ onNavigate }: { onNavigate?: (viewId: CanvasViewId) => void }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {CAPABILITIES.map(({ icon: Icon, label, desc, viewId }) => (
        <button key={viewId} type="button" title={desc} onClick={() => onNavigate?.(viewId)}
          className="group flex flex-col items-center gap-2 rounded-xl border border-border/50 bg-card/30 px-3 py-4 transition-colors hover:bg-accent/20">
          <Icon className="h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" aria-hidden />
          <span className="text-xs font-medium text-foreground/80">{label}</span>
        </button>
      ))}
    </div>
  );
}
