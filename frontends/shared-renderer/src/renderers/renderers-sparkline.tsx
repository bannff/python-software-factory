"use client";

import React from "react";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";

/* ── Color map ── */

const SPARK_COLORS: Record<string, string> = {
  indigo: "bg-indigo-500/40",
  blue: "bg-blue-500/40",
  emerald: "bg-emerald-500/40",
  purple: "bg-purple-500/40",
  red: "bg-red-500/40",
  orange: "bg-orange-500/40",
  yellow: "bg-yellow-500/40",
};

const STROKE_COLORS: Record<string, string> = {
  indigo: "stroke-indigo-500",
  blue: "stroke-blue-500",
  emerald: "stroke-emerald-500",
  purple: "stroke-purple-500",
  red: "stroke-red-500",
  orange: "stroke-orange-500",
  yellow: "stroke-yellow-500",
};

export type SparklineProps = {
  data?: number[];
  variant?: "bar" | "line";
  color?: string;
  height?: number;
  max_points?: number;
};

export function SparklineInline({ data, variant = "bar", color = "indigo", height = 32, max_points = 20 }: SparklineProps) {
  if (!data || data.length === 0) return null;
  const pts = data.slice(-max_points);
  const maxVal = Math.max(...pts, 1);

  if (variant === "line") {
    const w = pts.length * 6;
    const points = pts
      .map((v, i) => `${i * (w / Math.max(pts.length - 1, 1))},${height - (v / maxVal) * height}`)
      .join(" ");
    return (
      <svg width={w} height={height} className="shrink-0">
        <polyline
          points={points}
          fill="none"
          className={cn(STROKE_COLORS[color] ?? STROKE_COLORS.indigo)}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }

  // Bar variant (default)
  return (
    <div className="flex items-end gap-px" style={{ height }}>
      {pts.map((v, i) => (
        <div
          key={i}
          className={cn("flex-1 rounded-sm", SPARK_COLORS[color] ?? SPARK_COLORS.indigo)}
          style={{ height: `${(v / maxVal) * 100}%` }}
        />
      ))}
    </div>
  );
}

export function SparklineRenderer({ node }: RendererProps) {
  const p = node.props as SparklineProps;
  return <SparklineInline {...p} />;
}
