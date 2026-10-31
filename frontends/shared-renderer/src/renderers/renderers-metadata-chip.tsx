"use client";

import React from "react";
import { cn } from "../lib/utils";
import {
  CopyChip, TipChip, PromptChip, PillsChip, ThresholdChip,
  scoreColor, fmtTime,
} from "./renderers-metadata-chip-parts";

/* ── Types ── */

export type MetadataRenderAs =
  | "copy_id" | "popover" | "pills" | "relative_time"
  | "score" | "model_chip" | "threshold" | "default";

export type MetadataChipEntry = {
  label: string;
  value?: unknown;
  path?: string;
  render_as?: MetadataRenderAs;
  zone?: "config" | "identity";
};

/* ── Main MetadataChip ── */

export function MetadataChip({ entry, val }: { entry: MetadataChipEntry; val: unknown }) {
  const strVal = val != null ? String(val) : "";
  const renderAs = entry.render_as ?? "default";

  if (renderAs === "copy_id") return <CopyChip label={entry.label} value={strVal} />;

  if (renderAs === "model_chip") {
    const short = strVal.includes(".") ? strVal.split(".").slice(-2).join(".") : strVal;
    return <TipChip label={entry.label} short={short} full={strVal} />;
  }

  if (renderAs === "popover") return <PromptChip label={entry.label} value={strVal} />;

  if (renderAs === "pills") {
    const arr = Array.isArray(val) ? val.map(String) : [strVal];
    return <PillsChip label={entry.label} values={arr} />;
  }

  if (renderAs === "relative_time") return <TipChip label={entry.label} short={fmtTime(strVal)} full={strVal} />;

  if (renderAs === "score") {
    const num = parseFloat(strVal);
    const display = isNaN(num) ? strVal : `${Math.round(num * 100)}%`;
    return (
      <span className="flex items-center gap-1">
        <span className="text-muted-foreground/50">{entry.label}:</span>
        <span className={cn("font-semibold text-[11px]", !isNaN(num) && scoreColor(num))}>{display}</span>
      </span>
    );
  }

  if (renderAs === "threshold") return <ThresholdChip label={entry.label} val={val} />;

  return (
    <span className="flex items-center gap-1">
      <span className="text-muted-foreground/50">{entry.label}:</span>
      <span className="text-foreground/70">{strVal}</span>
    </span>
  );
}
