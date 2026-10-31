"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { BookOpen, Loader2, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { useKnowledge } from "./use-knowledge";

/**
 * Knowledge library (feature-map row 38): the document library backing
 * the KB brick. Browse/search, ingest, delete — all through tools that
 * already existed (``kb_list_documents``/``kb_search``/``kb_ingest``/
 * ``kb_delete_document``/``kb_get_collection_stats``); this view was the
 * only missing piece, same shape as the Memory browser's own history.
 *
 * Entities/graph (the rest of row 38's upstream description) are already
 * reachable via the Graph canvas's own KB-entity types once documents are
 * ingested with ``extract_entities`` — no separate surface needed here,
 * mirroring how row 46 (Explore memory) closed by reusing Graph rather
 * than building a second visualizer.
 */
export default function KnowledgeView() {
  const { documents, stats, loading, error, query, search, ingest, remove, refresh } = useKnowledge();
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [content, setContent] = useState("");
  const [source, setSource] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);

  const onSearchChange = (event: ChangeEvent<HTMLInputElement>) => search(event.target.value);

  const onDelete = async (documentId: string) => {
    setPendingDelete(documentId);
    await remove(documentId);
    setPendingDelete(null);
  };

  const onIngest = async (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) return;
    setIngesting(true);
    setIngestError(null);
    const ok = await ingest(content.trim(), source.trim() || undefined);
    setIngesting(false);
    if (ok) { setContent(""); setSource(""); setAdding(false); }
    else setIngestError("Couldn't add that document. Try again.");
  };

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="knowledge-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Knowledge</p>
          <h1 id="knowledge-title" className="mt-1 text-2xl font-semibold tracking-tight">Knowledge Library</h1>
          <p className="mt-1 text-sm text-muted-foreground">Documents your agents can search and cite.</p>
        </div>
        <div className="flex gap-1">
          <button type="button" onClick={() => setAdding((value) => !value)} aria-label="Add a new document"
            className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
            <Plus className="h-4 w-4" />
          </button>
          <button type="button" onClick={refresh} aria-label="Refresh knowledge library"
            className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Knowledge library statistics">
          <div className="rounded-lg border border-border/60 bg-card/30 p-3">
            <p className="text-xs text-muted-foreground">Documents</p>
            <p className="text-lg font-semibold">{stats.documentCount}</p>
          </div>
          <div className="rounded-lg border border-border/60 bg-card/30 p-3">
            <p className="text-xs text-muted-foreground">Total size</p>
            <p className="text-lg font-semibold">{(stats.totalSizeBytes / 1024).toFixed(1)} KB</p>
          </div>
        </div>
      )}

      {adding && (
        <form onSubmit={onIngest} className="rounded-xl border border-border/60 bg-card/20 p-4" aria-label="Add document">
          <label className="grid gap-1 text-xs text-muted-foreground">Content
            <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={4}
              placeholder="Paste or write the document content…"
              className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-sm text-foreground" /></label>
          <label className="mt-3 grid gap-1 text-xs text-muted-foreground">Source (optional)
            <input value={source} onChange={(event) => setSource(event.target.value)} placeholder="e.g. a filename or URL"
              className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-sm text-foreground" /></label>
          {ingestError && <p role="alert" className="mt-2 text-xs text-destructive">{ingestError}</p>}
          <div className="mt-3 flex gap-2">
            <button type="submit" disabled={ingesting || !content.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
              {ingesting && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Add document</button>
            <button type="button" onClick={() => setAdding(false)} className="rounded-md border border-border/60 px-3 py-2 text-xs">Cancel</button>
          </div>
        </form>
      )}

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input type="search" value={query} onChange={onSearchChange} placeholder="Search knowledge…"
          aria-label="Search knowledge library"
          className="w-full rounded-lg border border-border/60 bg-background py-2 pl-9 pr-3 text-sm outline-none focus:border-violet-400/60" />
      </div>

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Knowledge library unavailable right now.</span>
          <button type="button" onClick={refresh} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && documents.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading knowledge library…
        </div>
      )}

      {!loading && !error && documents.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 p-10 text-center">
          <BookOpen className="h-8 w-8 text-violet-400/70" />
          <h2 className="mt-3 font-medium">{query ? "No matches" : "No documents yet"}</h2>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            {query ? "Try a different search." : "Add a document above so your agents can search and cite it."}
          </p>
        </div>
      )}

      {!error && documents.length > 0 && (
        <ul className="flex flex-col gap-2" role="list" aria-label="Knowledge documents">
          {documents.map((document) => (
            <li key={document.id} role="listitem" className="flex items-start justify-between gap-3 rounded-lg border border-border/60 bg-card/30 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <code className="text-[10px]">{document.id}</code>
                  {document.source && <span>{document.source}</span>}
                  {document.score !== undefined && <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-violet-300">{(document.score * 100).toFixed(0)}% match</span>}
                </div>
                {document.content && <p className="mt-1.5 line-clamp-3 text-sm">{document.content}</p>}
              </div>
              <button type="button" onClick={() => onDelete(document.id)} disabled={pendingDelete === document.id}
                aria-label={`Delete document ${document.id}`}
                className="shrink-0 rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:opacity-50">
                {pendingDelete === document.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
