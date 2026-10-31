"use client";

import React, { useState } from "react";
import { Copy, Check } from "lucide-react";
import { cn } from "../lib/utils";
import * as Tooltip from "@radix-ui/react-tooltip";
import * as Collapsible from "@radix-ui/react-collapsible";

export const JUDGE_COLORS: Record<string, string> = {
  output: "bg-purple-500/15 text-purple-300",
  helpfulness: "bg-blue-500/15 text-blue-300",
  faithfulness: "bg-blue-500/15 text-blue-300",
  coherence: "bg-blue-500/15 text-blue-300",
  conciseness: "bg-blue-500/15 text-blue-300",
  harmfulness: "bg-blue-500/15 text-blue-300",
  response_relevance: "bg-blue-500/15 text-blue-300",
  tool_selection: "bg-blue-500/15 text-blue-300",
  tool_parameter: "bg-blue-500/15 text-blue-300",
  trajectory: "bg-emerald-500/15 text-emerald-300",
  interactions: "bg-emerald-500/15 text-emerald-300",
  goal_success: "bg-emerald-500/15 text-emerald-300",
};

export function scoreColor(v: number): string {
  if (v >= 0.8) return "text-emerald-400";
  if (v >= 0.5) return "text-amber-400";
  return "text-red-400";
}

export function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

export function CopyChip({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <span className="flex items-center gap-1 group">
      <span className="text-muted-foreground/50">{label}:</span>
      <span className="font-mono text-foreground/70">{value.slice(0, 12)}</span>
      <button onClick={copy} className="opacity-0 group-hover:opacity-100 transition-opacity">
        {copied ? <Check className="h-2.5 w-2.5 text-emerald-400" /> : <Copy className="h-2.5 w-2.5 text-muted-foreground/60 hover:text-foreground" />}
      </button>
    </span>
  );
}

export function TipChip({ label, short, full }: { label: string; short: string; full: string }) {
  return (
    <Tooltip.Provider delayDuration={300}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <span className="flex items-center gap-1 cursor-default">
            <span className="text-muted-foreground/50">{label}:</span>
            <span className="font-mono bg-muted/40 rounded px-1 text-foreground/70 truncate max-w-[120px]">{short}</span>
          </span>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content className="z-50 max-w-xs rounded bg-popover border border-border px-2 py-1 text-[10px] text-popover-foreground shadow-md break-all" sideOffset={4}>
            {full}
            <Tooltip.Arrow className="fill-border" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}

export function PromptChip({ label, value }: { label: string; value: string }) {
  const [open, setOpen] = useState(false);
  const short = value.length > 55 ? value.slice(0, 55) + "…" : value;
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger asChild>
        <button className="flex items-center gap-1 text-left group">
          <span className="text-muted-foreground/50">{label}:</span>
          <span className="text-foreground/70 group-hover:text-foreground transition-colors">{open ? value : short}</span>
        </button>
      </Collapsible.Trigger>
    </Collapsible.Root>
  );
}

export function PillsChip({ label, values }: { label: string; values: string[] }) {
  return (
    <span className="flex items-center gap-1 flex-wrap">
      <span className="text-muted-foreground/50">{label}:</span>
      {values.map((v) => (
        <span key={v} className={cn("rounded-full px-1.5 py-0.5 text-[9px] font-medium", JUDGE_COLORS[v] ?? "bg-muted/40 text-muted-foreground")}>{v}</span>
      ))}
    </span>
  );
}

export function ThresholdChip({ label, val }: { label: string; val: unknown }) {
  const obj = val && typeof val === "object" ? val as Record<string, unknown> : null;
  const warn = obj ? obj.warning : null;
  const crit = obj ? obj.critical : null;
  if (warn == null && crit == null) {
    return <span className="flex items-center gap-1"><span className="text-muted-foreground/50">{label}:</span><span className="text-foreground/70">{String(val)}</span></span>;
  }
  return (
    <span className="flex items-center gap-1">
      <span className="text-muted-foreground/50">{label}:</span>
      {warn != null && <span className="flex items-center gap-0.5 text-amber-400 font-semibold"><span className="text-[9px]">⚠</span>{String(warn)}</span>}
      {warn != null && crit != null && <span className="text-muted-foreground/30">/</span>}
      {crit != null && <span className="flex items-center gap-0.5 text-red-400 font-semibold"><span className="text-[9px]">✗</span>{String(crit)}</span>}
    </span>
  );
}
