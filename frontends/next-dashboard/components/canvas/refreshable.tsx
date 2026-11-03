"use client";

import { useState, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";

/** Server-driven views fetch once on mount; remounting on demand refetches all of them. */
export function Refreshable({ label, children }: { label: string; children: ReactNode }) {
  const [generation, setGeneration] = useState(0);
  return (
    <div className="relative">
      <button type="button" aria-label={`Refresh ${label}`} title={`Refresh ${label}`}
        onClick={() => setGeneration((g) => g + 1)}
        className="absolute right-3 top-2 z-10 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent/40 hover:text-foreground">
        <RefreshCw className="h-3.5 w-3.5" aria-hidden />
      </button>
      <div key={generation}>{children}</div>
    </div>
  );
}
