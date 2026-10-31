"use client";

import { useState, type ChangeEvent } from "react";
import { BrainCircuit, Check, GitBranch, History, Loader2, Pencil, RefreshCw, Search, Trash2, X } from "lucide-react";
import { useMemory } from "./use-memory";
import EmbeddingsCard from "./embeddings-card";
import BackupCard from "./backup-card";
import RecallInspectPanel from "./recall-inspect-panel";
import MemoryHistoryPanel from "./history-panel";
import type { MemoryScopeFilter, MemoryType } from "./memory-types";

const TYPE_OPTIONS: Array<{ value: MemoryType | "all"; label: string }> = [
  { value: "all", label: "All types" },
  { value: "short_term", label: "Short-term" },
  { value: "long_term", label: "Long-term" },
  { value: "episodic", label: "Episodic" },
];

const SCOPE_OPTIONS: Array<{ value: MemoryScopeFilter; label: string }> = [
  { value: "own", label: "Own + shared" },
  { value: "shared", label: "Shared only" },
];

/**
 * Memory browser (feature-map row 43 — read path, single correction, and
 * bulk delete of matched memories; row 49 Episodic search). Paged list,
 * text search, memory-type filter, a stats panel, inline correction, and
 * bulk delete over the current filter — all backed by real tools
 * (``memory_list``/``memory_retrieve``/``memory_stats``/``memory_update``/
 * ``memory_bulk_preview``/``memory_bulk_delete``) regardless of which
 * storage backend is active.
 *
 * Bulk delete is owner-scoped: "bulk delete of matched memories only, no
 * bulk content edit" (owner ruling) — there is no bulk-edit affordance by
 * design, matching row 45's own bulk-edit deferral on the identical
 * reasoning ("the curator owns bulk correction").
 */
export default function MemoryView() {
  const {
    memories, stats, loading, error, query, typeFilter, scopeFilter,
    search, filterByType, filterByScope, remove, correct,
    previewBulkDelete, bulkDelete, refresh,
  } = useMemory();
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const [inspecting, setInspecting] = useState<string | null>(null);
  const [viewingHistory, setViewingHistory] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [bulkPreview, setBulkPreview] = useState<{ count: number } | null>(null);
  const [bulkPreviewing, setBulkPreviewing] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkNotice, setBulkNotice] = useState<string | null>(null);

  const onSearchChange = (event: ChangeEvent<HTMLInputElement>) => search(event.target.value);
  const onTypeChange = (event: ChangeEvent<HTMLSelectElement>) => filterByType(event.target.value as MemoryType | "all");
  const onScopeChange = (event: ChangeEvent<HTMLSelectElement>) => filterByScope(event.target.value as MemoryScopeFilter);

  const onDelete = async (memoryId: string) => {
    setPendingDelete(memoryId);
    await remove(memoryId);
    setPendingDelete(null);
  };

  const armBulkDelete = async () => {
    setBulkPreviewing(true);
    setBulkError(null);
    setBulkNotice(null);
    const result = await previewBulkDelete();
    setBulkPreviewing(false);
    if (result.error) {
      setBulkError(result.error);
      return;
    }
    setBulkPreview({ count: result.count });
  };

  const cancelBulkDelete = () => {
    setBulkPreview(null);
    setBulkError(null);
  };

  const confirmBulkDelete = async () => {
    setBulkDeleting(true);
    const failure = await bulkDelete();
    setBulkDeleting(false);
    if (failure) {
      setBulkError(failure);
      return;
    }
    setBulkNotice(`Deleted ${bulkPreview?.count ?? 0} matching memories.`);
    setBulkPreview(null);
  };

  const startEdit = (memoryId: string, currentContent: string) => {
    setEditing(memoryId);
    setDraft(currentContent);
    setSaveError(null);
  };

  const cancelEdit = () => {
    setEditing(null);
    setDraft("");
    setSaveError(null);
  };

  const saveEdit = async (memoryId: string) => {
    setSaving(true);
    const failure = await correct(memoryId, draft);
    setSaving(false);
    if (failure) {
      setSaveError(failure);
      return;
    }
    setEditing(null);
    setDraft("");
    setSaveError(null);
  };

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="memory-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Memory</p>
          <h1 id="memory-title" className="mt-1 text-2xl font-semibold tracking-tight">Memory Browser</h1>
          <p className="mt-1 text-sm text-muted-foreground">Facts, rules and experiences Companion X has stored for you.</p>
        </div>
        <button type="button" onClick={refresh} aria-label="Refresh memory" className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Memory statistics">
          <div className="rounded-lg border border-border/60 bg-card/30 p-3">
            <p className="text-xs text-muted-foreground">Total</p>
            <p className="text-lg font-semibold">{stats.totalMemories}</p>
          </div>
          {Object.entries(stats.byType).map(([type, count]) => (
            <div key={type} className="rounded-lg border border-border/60 bg-card/30 p-3">
              <p className="text-xs text-muted-foreground">{type.replace("_", " ")}</p>
              <p className="text-lg font-semibold">{count}</p>
            </div>
          ))}
        </div>
      )}

      <EmbeddingsCard />
      <BackupCard />

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-56">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={query}
            onChange={onSearchChange}
            placeholder="Search memory…"
            aria-label="Search memory"
            className="w-full rounded-lg border border-border/60 bg-background py-2 pl-9 pr-3 text-sm outline-none focus:border-violet-400/60"
          />
        </div>
        <select
          value={typeFilter}
          onChange={onTypeChange}
          aria-label="Filter by memory type"
          className="rounded-lg border border-border/60 bg-background px-3 py-2 text-sm outline-none focus:border-violet-400/60"
        >
          {TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <select
          value={scopeFilter}
          onChange={onScopeChange}
          aria-label="Filter by memory scope"
          className="rounded-lg border border-border/60 bg-background px-3 py-2 text-sm outline-none focus:border-violet-400/60"
        >
          {SCOPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        {!bulkPreview && (
          <button
            type="button"
            onClick={armBulkDelete}
            disabled={bulkPreviewing}
            className="flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-2 text-xs text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:opacity-50"
          >
            {bulkPreviewing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />} Delete matching…
          </button>
        )}
      </div>

      {bulkPreview && (
        <div role="alertdialog" aria-label="Confirm bulk delete" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>
            This will delete <strong>{bulkPreview.count}</strong> memor{bulkPreview.count === 1 ? "y" : "ies"} matching the current search and filters.
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={confirmBulkDelete}
              disabled={bulkDeleting || bulkPreview.count === 0}
              className="rounded-md border border-destructive/40 px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
            >
              {bulkDeleting ? "Deleting…" : `Delete ${bulkPreview.count}`}
            </button>
            <button type="button" onClick={cancelBulkDelete} disabled={bulkDeleting} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50 disabled:opacity-50">
              Cancel
            </button>
          </div>
        </div>
      )}
      {bulkError && <p role="alert" className="text-xs text-destructive">{bulkError}</p>}
      {bulkNotice && !bulkError && <p className="text-xs text-muted-foreground">{bulkNotice}</p>}

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Memory unavailable right now.</span>
          <button type="button" onClick={refresh} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && memories.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading memory…
        </div>
      )}

      {!loading && !error && memories.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 p-10 text-center">
          <BrainCircuit className="h-8 w-8 text-violet-400/70" />
          <h2 className="mt-3 font-medium">{query ? "No matches" : "No memories yet"}</h2>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            {query ? "Try a different search or clear the filter." : "As Companion X learns things about you, they'll show up here."}
          </p>
        </div>
      )}

      {!error && memories.length > 0 && (
        <ul className="flex flex-col gap-2" role="list" aria-label="Memories">
          {memories.map((memory) => (
            <li key={memory.id} role="listitem" className="rounded-lg border border-border/60 bg-card/30 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-violet-300">{memory.memoryType.replace("_", " ")}</span>
                    <span>{memory.category}</span>
                    {typeof memory.metadata.scope === "string" && (
                      <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-sky-300">{memory.metadata.scope}</span>
                    )}
                    {typeof memory.metadata.agent === "string" && (
                      <span>· {memory.metadata.agent}</span>
                    )}
                    {memory.createdAt && <span>{new Date(memory.createdAt).toLocaleString()}</span>}
                    {memory.updatedAt && <span>· edited {new Date(memory.updatedAt).toLocaleString()}</span>}
                  </div>
                  {editing === memory.id ? (
                    <div className="mt-1.5">
                      <textarea
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        aria-label={`Edit memory ${memory.id}`}
                        rows={3}
                        className="w-full rounded-lg border border-violet-400/50 bg-background p-2 text-sm outline-none focus:border-violet-400"
                      />
                      {saveError && <p className="mt-1 text-xs text-destructive">{saveError}</p>}
                    </div>
                  ) : (
                    <p className="mt-1.5 text-sm">{memory.content}</p>
                  )}
                </div>
                <div className="flex shrink-0 gap-1.5">
                  {editing === memory.id ? (
                    <>
                      <button
                        type="button"
                        onClick={() => saveEdit(memory.id)}
                        disabled={saving || !draft.trim()}
                        aria-label={`Save correction for memory ${memory.id}`}
                        className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-emerald-400/50 hover:text-emerald-300 disabled:opacity-50"
                      >
                        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        disabled={saving}
                        aria-label={`Cancel editing memory ${memory.id}`}
                        className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:bg-muted/50 disabled:opacity-50"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => startEdit(memory.id, memory.content)}
                        aria-label={`Edit memory ${memory.id}`}
                        className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-violet-400/50 hover:text-violet-300"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setInspecting(inspecting === memory.id ? null : memory.id)}
                        aria-label={`Inspect recall for memory ${memory.id}`}
                        aria-pressed={inspecting === memory.id}
                        className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-violet-400/50 hover:text-violet-300"
                      >
                        <GitBranch className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setViewingHistory(viewingHistory === memory.id ? null : memory.id)}
                        aria-label={`View history for memory ${memory.id}`}
                        aria-pressed={viewingHistory === memory.id}
                        className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-sky-400/50 hover:text-sky-300"
                      >
                        <History className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(memory.id)}
                        disabled={pendingDelete === memory.id}
                        aria-label={`Delete memory ${memory.id}`}
                        className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:opacity-50"
                      >
                        {pendingDelete === memory.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                      </button>
                    </>
                  )}
                </div>
              </div>
              {inspecting === memory.id && (
                <RecallInspectPanel memoryId={memory.id} onClose={() => setInspecting(null)} />
              )}
              {viewingHistory === memory.id && (
                <MemoryHistoryPanel memoryId={memory.id} onClose={() => setViewingHistory(null)} />
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
