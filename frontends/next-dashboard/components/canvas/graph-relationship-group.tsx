"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

export interface EdgeInfo {
  direction: "→" | "←";
  otherName: string;
  otherId: string;
}

export function RelGroup({ label, edges: items }: { label: string; edges: EdgeInfo[] }) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs font-medium text-foreground mb-1"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] text-violet-400">{label}</span>
        <span className="text-muted-foreground text-[10px]">({items.length})</span>
      </button>
      {open && (
        <div className="ml-4 space-y-0.5">
          {items.map((edge, index) => (
            <div key={index} className="text-[11px] text-muted-foreground truncate">
              <span className="text-foreground/60">{edge.direction}</span>{" "}
              <span className="text-foreground/80">{edge.otherName || edge.otherId}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
