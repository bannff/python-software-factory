"use client";

import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Finding } from "@/lib/types";
import { SEV_BAR_COLORS, arnFragment } from "./findings-view-style";

/** The thing the finding is about, in its shortest readable form. */
function subjectOf(f: Finding): string | undefined {
  if (f.affected_resource_arn) return arnFragment(f.affected_resource_arn);
  return f.resource && f.resource !== "unknown" ? f.resource : undefined;
}

/** One calm line per finding: severity dot, title, muted "kind · subject". */
export function FindingRow({ finding, expanded, onToggle }: {
  finding: Finding; expanded: boolean; onToggle: () => void;
}) {
  const subject = subjectOf(finding);
  return (
    <button type="button" onClick={onToggle} aria-expanded={expanded} title={finding.severity}
      className="flex w-full items-center gap-3 rounded-lg border border-border/50 bg-card/30 px-3 py-2.5 text-left transition-colors hover:bg-accent/20">
      <span className={cn("h-2 w-2 shrink-0 rounded-full", SEV_BAR_COLORS[finding.severity])} aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{finding.title}</span>
        <span className="block truncate text-[11px] text-muted-foreground/70">
          {[finding.type, subject].filter(Boolean).join(" · ")}
        </span>
      </span>
      <ChevronRight className={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-90")} />
    </button>
  );
}
