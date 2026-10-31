"use client";

import { colorForType } from "@/lib/hooks/use-graph-data";
import { cn } from "@/lib/utils";

interface GraphTypeFiltersProps {
  typeCounts: [string, number][];
  hiddenTypes: Set<string>;
  visibleCount: number;
  onToggleType: (type: string) => void;
}

export function GraphTypeFilters({ typeCounts, hiddenTypes, visibleCount, onToggleType }: GraphTypeFiltersProps) {
  if (typeCounts.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5 border-b border-border/50 bg-card/5 px-4 py-1.5 overflow-x-auto">
      <span className="text-[10px] text-muted-foreground mr-1 shrink-0">
        {visibleCount} visible
      </span>
      {typeCounts.map(([type, count]) => (
        <button
          key={type}
          onClick={() => onToggleType(type)}
          className={cn(
            "flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-medium transition-all shrink-0",
            hiddenTypes.has(type)
              ? "bg-muted/30 text-muted-foreground/50 line-through"
              : "",
          )}
          style={
            hiddenTypes.has(type)
              ? undefined
              : { backgroundColor: colorForType(type) + "18", color: colorForType(type) }
          }
        >
          {!hiddenTypes.has(type) && (
            <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: colorForType(type) }} />
          )}
          {count} {type}
        </button>
      ))}
    </div>
  );
}
