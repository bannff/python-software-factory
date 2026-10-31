"use client";

import React from "react";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";

/* ── Color maps ── */

const DOT_COLORS: Record<string, string> = {
  emerald: "bg-emerald-500",
  yellow: "bg-yellow-500",
  red: "bg-red-500",
  blue: "bg-blue-500",
  gray: "bg-gray-500/30",
  "blue-pulse": "bg-blue-500 animate-pulse",
};

const TREND_COLORS: Record<string, { char: string; cls: string }> = {
  up: { char: "↑", cls: "text-emerald-400" },
  down: { char: "↓", cls: "text-red-400" },
  flat: { char: "→", cls: "text-muted-foreground" },
};

/* ── StatusDot ── */

type StatusDotProps = {
  value?: number | null;
  thresholds?: { warning?: number; critical?: number };
  states?: Record<string, string>;
  state?: string;
};

function resolveColor(props: StatusDotProps): string {
  const { value, thresholds, states, state } = props;
  // State-based (e.g. "completed" → "emerald")
  if (state != null && states) return DOT_COLORS[states[state] ?? "gray"] ?? DOT_COLORS.gray;
  // Threshold-based
  if (value == null) return DOT_COLORS.gray;
  const warn = thresholds?.warning;
  const crit = thresholds?.critical;
  if (warn != null && value >= warn) return DOT_COLORS.emerald;
  if (crit != null && value >= crit) return DOT_COLORS.yellow;
  if (crit != null && value < crit) return DOT_COLORS.red;
  return DOT_COLORS.emerald;
}

export function StatusDotInline(props: StatusDotProps) {
  return <span className={cn("h-2 w-2 rounded-full shrink-0", resolveColor(props))} />;
}

export function StatusDotRenderer({ node }: RendererProps) {
  const p = node.props as StatusDotProps;
  return <StatusDotInline {...p} />;
}

/* ── TrendBadge ── */

type TrendBadgeProps = {
  direction?: string;
  change_pct?: number | null;
  positive_is_good?: boolean;
};

export function TrendBadgeInline({ direction, change_pct, positive_is_good = true }: TrendBadgeProps) {
  const dir = direction ?? "flat";
  const base = TREND_COLORS[dir] ?? TREND_COLORS.flat;
  // Flip colors when positive_is_good is false
  const flip = !positive_is_good && dir !== "flat";
  const cls = flip
    ? dir === "up" ? "text-red-400" : "text-emerald-400"
    : base.cls;

  return (
    <span className="flex items-center gap-1 shrink-0">
      <span className={cn("text-xs", cls)}>{base.char}</span>
      {change_pct != null && (
        <span className="text-[10px] text-muted-foreground">
          {change_pct > 0 ? "+" : ""}{change_pct}%
        </span>
      )}
    </span>
  );
}

export function TrendBadgeRenderer({ node }: RendererProps) {
  const p = node.props as TrendBadgeProps;
  return <TrendBadgeInline {...p} />;
}
