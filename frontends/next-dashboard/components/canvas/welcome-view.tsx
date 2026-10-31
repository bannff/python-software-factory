"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Shield, Network, GitBranch, Beaker, BarChart3,
  Brain, Gamepad2, Link2, Container,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { callTool } from "@/lib/api";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";
import { ParticleText } from "@/components/ui/particle-text";
import type { CanvasViewId } from "@/lib/types";

interface WelcomeViewProps {
  onNavigate?: (viewId: CanvasViewId) => void;
}

const ROTATING_WORDS = [
  "Evals", "Findings", "Blockchain", "Machine Learning",
  "Sandbox", "Games", "Metrics", "Graph", "Timeline",
];

const CAPABILITIES: {
  icon: typeof Shield; label: string; desc: string; viewId: CanvasViewId;
}[] = [
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

interface StatusMetric {
  label: string; value: string | null; color?: string; loading: boolean;
}

export default function WelcomeView({ onNavigate }: WelcomeViewProps) {
  const { entries: live, connected } = useLiveToolStream();
  const [metrics, setMetrics] = useState<StatusMetric[]>([
    { label: "findings", value: null, loading: true },
    { label: "eval pass rate", value: null, loading: true },
    { label: "graph nodes", value: null, loading: true },
  ]);

  useEffect(() => {
    const update = (idx: number, value: string | null, color?: string) => {
      setMetrics((prev) =>
        prev.map((m, i) => (i === idx ? { ...m, value, color, loading: false } : m)),
      );
    };
    Promise.allSettled([
      // bd:python-factory-d4r37 — defensive call. If the security brick
      // isn't loaded (e.g. a domain project drops it from pyproject.toml),
      // the metric strip must gracefully degrade instead of throwing.
      callTool("security_security.list_persisted_findings", { limit: 50 })
        .then((r: unknown) => {
          const res = (r as Record<string, unknown>)?.result ?? r;
          const n = Number((res as Record<string, unknown>)?.count ?? 0);
          update(0, String(n), n > 0 ? "text-red-400" : "text-emerald-400");
        })
        .catch(() => {
          update(0, null, undefined);
        }),
      callTool("evals_list_run_results", {}).then((r: unknown) => {
        const res = (r as Record<string, unknown>)?.result ?? r;
        const latest = (res as Record<string, unknown>)?.latest as Record<string, unknown> | null;
        const rate = latest?.pass_rate != null ? `${Math.round(Number(latest.pass_rate) * 100)}%` : null;
        const color = latest?.pass_rate != null
          ? Number(latest.pass_rate) >= 0.8 ? "text-emerald-400"
            : Number(latest.pass_rate) >= 0.5 ? "text-amber-400" : "text-red-400"
          : undefined;
        update(1, rate, color);
      }).catch(() => {
        update(1, null, undefined);
      }),
      callTool("graph_get_stats", {}).then((r: unknown) => {
        const res = (r as Record<string, unknown>)?.result ?? r;
        const n = (res as Record<string, unknown>)?.node_count;
        update(2, n != null ? String(n) : null);
      }).catch(() => {
        update(2, null, undefined);
      }),
    ]);
  }, []);

  return (
    <div className="relative flex h-full flex-col items-center overflow-hidden">
      {/* Subtle bloom glow */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/4 -translate-x-1/2 -translate-y-1/2 h-[300px] w-[500px] rounded-full bg-violet-500/[0.06] blur-[100px]" />
        <div className="absolute left-1/3 top-3/4 -translate-x-1/2 h-[200px] w-[300px] rounded-full bg-blue-500/[0.04] blur-[80px]" />
      </div>

      {/* Hero section — centered */}
      <div className="flex flex-1 flex-col items-center justify-center max-w-lg">
        <ParticleText
          words={ROTATING_WORDS}
          interval={2500}
          className="relative z-10 text-4xl font-bold tracking-tight text-foreground/90"
        />
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="relative z-10 mt-6 text-[13px] text-muted-foreground/50 text-center leading-relaxed"
        >
          I build agentic systems for Information Security In Amazon that scale.
        </motion.p>
      </div>

      {/* Capability list */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="relative z-10 w-full max-w-xl mb-6 px-4"
      >
        <div className="grid grid-cols-1 gap-px rounded-lg border border-border/30 bg-border/20 overflow-hidden">
          {CAPABILITIES.map(({ icon: Icon, label, desc, viewId }) => (
            <button
              key={viewId}
              onClick={() => onNavigate?.(viewId)}
              className="flex items-center gap-3 bg-card/40 px-4 py-2.5 text-left hover:bg-accent/30 transition-colors group"
            >
              <Icon className="h-3.5 w-3.5 text-muted-foreground/40 group-hover:text-foreground/70 transition-colors shrink-0" />
              <span className="text-[12px] font-medium text-foreground/70 w-20 shrink-0">{label}</span>
              <span className="text-[11px] text-muted-foreground/40 group-hover:text-muted-foreground/60 transition-colors">{desc}</span>
            </button>
          ))}
        </div>
      </motion.div>

      {/* Status strip — anchored at bottom */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="relative z-10 flex items-center gap-4 px-4 py-2 mb-2"
      >
        <span className={cn(
          "h-1.5 w-1.5 rounded-full shrink-0",
          connected ? "bg-emerald-400 animate-pulse" : "bg-amber-400",
        )} />
        <span className="text-[10px] text-muted-foreground/40 tabular-nums">
          {live.length} live
        </span>
        <span className="text-border/30">·</span>
        {metrics.map((m) => (
          <span key={m.label} className="flex items-center gap-1 text-[10px]">
            <span className="text-muted-foreground/30">{m.label}</span>
            <span className={cn("font-medium tabular-nums", m.loading ? "text-muted-foreground/20" : (m.color ?? "text-foreground/50"))}>
              {m.loading ? "—" : (m.value ?? "—")}
            </span>
          </span>
        ))}
      </motion.div>
    </div>
  );
}
