"use client";

import { cn } from "@/lib/utils";

export type EntityKind = "run" | "brick" | "tx" | "session";

const KIND_STYLE: Record<EntityKind, string> = {
  run: "bg-sky-500/15 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300",
  brick: "bg-violet-500/15 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300",
  tx: "bg-amber-500/15 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  session: "bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
};

export interface EntityChipProps {
  kind: EntityKind;
  value: string;
  onClick?: (e: React.MouseEvent) => void;
}

export function EntityChip({ kind, value, onClick }: EntityChipProps) {
  const label = `${kind}:${value.length > 12 ? value.slice(0, 12) : value}`;

  if (!onClick) {
    return (
      <span
        aria-label={`${kind} ${value}`}
        className={cn(
          "inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium font-mono",
          KIND_STYLE[kind],
        )}
      >
        {label}
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Filter by ${kind} ${value}`}
      className={cn(
        "inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium font-mono transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60",
        "hover:brightness-125 cursor-pointer",
        KIND_STYLE[kind],
      )}
    >
      {label}
    </button>
  );
}
