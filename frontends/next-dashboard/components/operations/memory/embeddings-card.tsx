"use client";

import { useCallback, useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

interface EmbeddingStatus {
  backend: string; isGraphBackend: boolean; embedderConfigured: boolean;
  isSemantic: boolean; loadError: string | null; modelPath: string;
  dimensions: number; changeHint: string;
}

function statusFrom(raw: unknown): EmbeddingStatus {
  const v = unwrapToolData(raw) as Record<string, unknown>;
  if (typeof v.backend !== "string") throw new Error("Embedding status unavailable.");
  return {
    backend: v.backend, isGraphBackend: v.is_graph_backend === true,
    embedderConfigured: v.embedder_configured === true, isSemantic: v.is_semantic === true,
    loadError: typeof v.load_error === "string" ? v.load_error : null,
    modelPath: typeof v.model_path === "string" ? v.model_path : "",
    dimensions: typeof v.dimensions === "number" ? v.dimensions : 0,
    changeHint: typeof v.change_hint === "string" ? v.change_hint : "",
  };
}

/**
 * Memory browser → Embeddings card (feature-map row 50). The embedder is a
 * process-wide composition choice (`MEMORY_BACKEND`/`MEMORY_LOCAL_EMBED_MODEL`),
 * exactly like Settings → Browser's engine — this reports the EFFECTIVE state
 * truthfully rather than offering a live toggle that would either lie or need
 * a config-write capability this brick doesn't have.
 */
export default function EmbeddingsCard() {
  const [status, setStatus] = useState<EmbeddingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(statusFrom(await callTool("memory_get_embedding_status", {})));
      setError(null);
    } catch {
      setError("Embedding status unavailable.");
    }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  if (error) return <p role="alert" className="text-xs text-destructive">{error}</p>;
  if (!status) return null;

  const label = status.isSemantic ? "Semantic (local model)"
    : status.isGraphBackend ? "Keyword fallback (no model loaded)"
    : "Not enabled — using a non-graph backend";

  return (
    <section aria-labelledby="embeddings-card-title" className="rounded-lg border border-border/50 bg-card/30 p-4">
      <div className="flex items-center gap-2">
        <Cpu className="h-4 w-4 text-violet-400" />
        <h3 id="embeddings-card-title" className="text-sm font-medium">Embeddings</h3>
      </div>
      <p className={`mt-2 text-sm ${status.isSemantic ? "text-emerald-400" : "text-amber-400"}`}>{label}</p>
      {status.isGraphBackend && (
        <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
          <div className="rounded-md border border-border/30 px-3 py-2">
            <dt className="text-[10px] text-muted-foreground">Model path</dt>
            <dd className="m-0 truncate font-mono text-[11px]" title={status.modelPath}>{status.modelPath || "(none configured)"}</dd>
          </div>
          <div className="rounded-md border border-border/30 px-3 py-2">
            <dt className="text-[10px] text-muted-foreground">Dimensions</dt>
            <dd className="m-0 text-[11px]">{status.dimensions}</dd>
          </div>
        </dl>
      )}
      {status.loadError && status.loadError !== "not_graph_backend" && (
        <p className="mt-2 text-[11px] text-muted-foreground">Reason: {status.loadError}</p>
      )}
      <p className="mt-3 text-[11px] text-muted-foreground">To change: {status.changeHint}</p>
    </section>
  );
}
