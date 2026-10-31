"use client";

import { History, Loader2, RotateCcw } from "lucide-react";
import type { ArtifactVersion } from "./artifact-types";

export function ArtifactHistory({
  versions, loading, reverting, currentVersion, onRevert,
}: {
  versions: ArtifactVersion[]; loading: boolean; reverting: number | null;
  currentVersion: number; onRevert: (version: number) => void;
}) {
  return (
    <section aria-labelledby="artifact-history-title" className="space-y-3">
      <div className="flex items-center gap-2"><History className="h-4 w-4 text-violet-400" /><h3 id="artifact-history-title" className="text-sm font-medium">Version history</h3></div>
      {loading && versions.length === 0 ? <p className="text-xs text-muted-foreground">Loading versions…</p> : (
        <ol className="space-y-2">{versions.map((version) => {
          const current = version.version === currentVersion;
          return <li key={version.version} className="flex items-center justify-between gap-3 rounded-lg border border-border/50 bg-muted/10 px-3 py-2"><div><p className="text-xs font-medium">v{version.version}{current ? " · current" : ""}</p><p className="text-[11px] text-muted-foreground">{version.event_type} by {version.actor_kind}</p></div><button type="button" disabled={current || reverting !== null} onClick={() => onRevert(version.version)} aria-label={`Restore version ${version.version}`} className="inline-flex items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground disabled:opacity-30">{reverting === version.version ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />} Restore</button></li>;
        })}</ol>
      )}
    </section>
  );
}
