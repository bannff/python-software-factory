"use client";

import { Clock } from "lucide-react";

/**
 * Rich body components for instrumented tool calls.
 *
 * v2 cutover note: chrome (icon + title + status pill + collapsible
 * chevron) is rendered by the shared <ToolCallCard> wrapper in
 * tool-renderers.tsx. These components return the *body only* — no
 * card border, no header — to avoid double-chrome inside the wrapper.
 */

interface KbHit {
  content: string;
  metadata: Record<string, unknown>;
  score: number;
}

export function KbSearchCard({ results }: { results: KbHit[] }) {
  if (!results?.length) {
    return <p className="text-xs text-muted-foreground">No results found.</p>;
  }
  return (
    <div className="space-y-2">
      {results.map((hit, i) => (
        <div key={i} className="rounded-lg border border-border/30 bg-background/50 p-3">
          <div className="flex items-start justify-between gap-2">
            <p className="text-xs text-foreground/90 line-clamp-3 flex-1">
              {hit.content}
            </p>
            <span className="shrink-0 rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-medium text-blue-400">
              {hit.score.toFixed(2)}
            </span>
          </div>
          {Object.keys(hit.metadata ?? {}).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {Object.entries(hit.metadata).slice(0, 4).map(([k, v]) => (
                <span key={k} className="rounded bg-muted/50 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {k}: {String(v)}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

interface CacheResult {
  key: string;
  value: unknown;
  ttl?: number;
  hit: boolean;
}

export function CacheGetCard({ data }: { data: CacheResult }) {
  const preview = JSON.stringify(data.value, null, 2);
  const truncated = preview.length > 200 ? preview.slice(0, 200) + "…" : preview;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <code className="rounded bg-muted/50 px-1.5 py-0.5 text-[11px] text-foreground/80">
          {data.key}
        </code>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
            data.hit
              ? "bg-green-500/15 text-green-400"
              : "bg-red-500/15 text-red-400"
          }`}
        >
          {data.hit ? "HIT" : "MISS"}
        </span>
        {data.ttl != null && (
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Clock className="h-3 w-3" />
            {data.ttl}s
          </span>
        )}
      </div>
      {data.hit && (
        <pre className="rounded-lg bg-background/50 border border-border/30 p-2 text-[11px] text-foreground/70 overflow-x-auto max-h-32">
          {truncated}
        </pre>
      )}
    </div>
  );
}

