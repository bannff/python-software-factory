"use client";

import React from "react";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";
import { ViewIcon } from "./renderers-icon";
import { resolve } from "./renderers-item-list-utils";
import { useToolData } from "./use-tool-data";

const INTENT_COLORS: Record<string, string> = {
  success: "text-emerald-400",
  warning: "text-amber-400",
  danger: "text-red-400",
  info: "text-sky-400",
  neutral: "text-foreground/90",
};

function extractMetricValue(data: unknown): string | null {
  if (data == null) return null;
  if (typeof data === "number" || typeof data === "string") return String(data);
  if (typeof data !== "object") return null;
  const obj = data as Record<string, unknown>;
  if (obj.value != null) return String(obj.value);
  if (obj.count != null) return String(obj.count);
  if (obj.status != null) return String(obj.status);
  if (obj.data_points != null) return String(obj.data_points);
  if (obj.definitions && Array.isArray(obj.definitions)) return String(obj.definitions.length);
  if (obj.items && Array.isArray(obj.items)) return String(obj.items.length);
  if (obj.result != null) return extractMetricValue(obj.result);
  return null;
}

/**
 * Compact single-line stat tile (bd:python-factory-3jcls.2).
 *
 * Was a full-width ~98px block (label above a text-2xl value), so seven
 * integers needed a scrollbar. Now it borrows the density idiom the
 * Experiments sub-tab already uses — one ``border-border/50 bg-card/30``
 * row, glyph + label + right-aligned value — and ``ComponentTree``
 * tiles consecutive metrics into a responsive grid. Same surface, same
 * palette, ~40px tall.
 */
export function MetricCardRenderer({ node }: RendererProps) {
  const { data_tool, data_path, label, value: fallback, icon, intent = "neutral", tooltip, className } =
    node.props as {
      data_tool?: string; data_path?: string; label?: string; value?: string; icon?: string;
      intent?: string; tooltip?: string; className?: string;
    };
  const { data, loading, error } = useToolData(data_tool);
  const selected = data_path && data && typeof data === "object"
    ? resolve(data as Record<string, unknown>, data_path) : data;
  const displayValue = extractMetricValue(selected) ?? fallback ?? "—";
  const colorClass = INTENT_COLORS[intent] ?? INTENT_COLORS.neutral;
  const shell = "rounded-lg border border-border/50 bg-card/30 px-3 py-2.5";

  if (loading) {
    return (
      <div className={cn(shell, "animate-pulse", className)}>
        <div className="flex items-center gap-2">
          <div className="h-3 flex-1 rounded bg-muted" />
          <div className="h-3 w-6 rounded bg-muted" />
        </div>
      </div>
    );
  }

  return (
    <div className={cn(shell, className)} title={tooltip}>
      <div className="flex items-center gap-2">
        <ViewIcon name={icon} className="h-3.5 w-3.5 text-muted-foreground" textClassName="text-xs" />
        <span
          title={label}
          className="min-w-0 flex-1 truncate text-xs font-medium text-muted-foreground"
        >
          {label ?? "Metric"}
        </span>
        <span className={cn("shrink-0 text-sm font-semibold tabular-nums", error ? "text-destructive" : colorClass)}>
          {error ? "Error" : displayValue}
        </span>
      </div>
      {error && <p className="mt-1 truncate text-[10px] text-destructive">{error}</p>}
    </div>
  );
}
