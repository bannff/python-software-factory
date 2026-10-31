"use client";

import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MetricTone } from "@/lib/runtime-metrics-summary";

export interface MetricCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
  tone?: MetricTone;
  active?: boolean;
  onClick?: () => void;
}

export function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = "neutral",
  active = false,
  onClick,
}: MetricCardProps) {
  const content = (
    <>
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-4 w-4" />
        <span className="text-xs font-medium">{label}</span>
        {onClick && (
          <ChevronRight className={cn("ml-auto h-3.5 w-3.5 transition-transform", active && "rotate-90")} />
        )}
      </div>
      <p className={cn(
        "mt-3 text-3xl font-semibold tracking-tight",
        tone === "good" && "text-emerald-400",
        tone === "warn" && "text-amber-400",
        tone === "bad" && "text-red-400",
        tone === "neutral" && "text-foreground/90",
      )}>
        {value}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
      {onClick && <p className="mt-2 text-[10px] text-sky-300/80">Click to inspect backing events</p>}
    </>
  );

  if (!onClick) {
    return (
      <div className="rounded-xl border border-border/50 bg-card/30 p-4">
        {content}
      </div>
    );
  }

  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-xl border border-border/50 bg-card/30 p-4 text-left transition-colors hover:bg-accent/20",
        active && "ring-1 ring-sky-400/40 bg-accent/15",
      )}
    >
      {content}
    </button>
  );
}
