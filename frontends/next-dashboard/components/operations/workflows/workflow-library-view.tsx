"use client";

import { useState, type FormEvent } from "react";
import { Loader2, Play, Plus, RefreshCw, Trash2, Workflow as WorkflowIcon } from "lucide-react";
import { useWorkflowLibrary } from "./use-workflow-library";

/**
 * Workflow library (feature-map row 42): saved dynamic-workflow definitions
 * and their runs. A thin FE view over the already-complete Workflow brick
 * (definitions load from real on-disk YAML at process start) — this view
 * was the only missing piece.
 */
export default function WorkflowLibraryView() {
  const { definitions, runs, canAuthor, loading, error, refresh,
    createDefinition, deleteDefinition, startRun, cancelRun } = useWorkflowLibrary();
  const [adding, setAdding] = useState(false);
  const [id, setId] = useState("");
  const [yamlText, setYamlText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!id.trim() || !yamlText.trim()) return;
    setSaving(true);
    setSaveError(null);
    const err = await createDefinition(id.trim(), yamlText);
    setSaving(false);
    if (err) setSaveError(err);
    else { setId(""); setYamlText(""); setAdding(false); }
  };

  const onDelete = async (definitionId: string) => {
    setPending(definitionId);
    await deleteDefinition(definitionId);
    setPending(null);
  };

  const onRun = async (definitionId: string) => {
    setPending(definitionId);
    await startRun(definitionId);
    setPending(null);
  };

  const onCancel = async (runId: string) => {
    setPending(runId);
    await cancelRun(runId);
    setPending(null);
  };

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="workflows-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Workflows</p>
          <h1 id="workflows-title" className="mt-1 text-2xl font-semibold tracking-tight">Workflow Library</h1>
          <p className="mt-1 text-sm text-muted-foreground">Saved multi-step workflow definitions and their runs.</p>
        </div>
        <div className="flex gap-1">
          {canAuthor && <button type="button" onClick={() => setAdding((v) => !v)} aria-label="Add a new workflow definition"
            className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
            <Plus className="h-4 w-4" />
          </button>}
          <button type="button" onClick={() => void refresh()} aria-label="Refresh workflow library"
            className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {adding && (
        <form onSubmit={onCreate} className="rounded-xl border border-border/60 bg-card/20 p-4" aria-label="Add workflow definition">
          <label className="grid gap-1 text-xs text-muted-foreground">ID
            <input value={id} onChange={(event) => setId(event.target.value)} placeholder="e.g. daily-digest"
              className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-sm text-foreground" /></label>
          <label className="mt-3 grid gap-1 text-xs text-muted-foreground">Definition (YAML)
            <textarea value={yamlText} onChange={(event) => setYamlText(event.target.value)} rows={8}
              placeholder={"name: Daily digest\nsteps:\n  - id: start\n    kind: task\n    ..."}
              className="rounded-md border border-border/60 bg-background/50 px-3 py-2 font-mono text-xs text-foreground" /></label>
          {saveError && <p role="alert" className="mt-2 text-xs text-destructive">{saveError}</p>}
          <div className="mt-3 flex gap-2">
            <button type="submit" disabled={saving || !id.trim() || !yamlText.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Save definition</button>
            <button type="button" onClick={() => setAdding(false)} className="rounded-md border border-border/60 px-3 py-2 text-xs">Cancel</button>
          </div>
        </form>
      )}

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Workflow library unavailable right now.</span>
          <button type="button" onClick={() => void refresh()} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && definitions.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading workflow library…
        </div>
      )}

      {!loading && !error && definitions.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 p-10 text-center">
          <WorkflowIcon className="h-8 w-8 text-violet-400/70" />
          <h2 className="mt-3 font-medium">No workflows yet</h2>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">Save a workflow definition to run it here.</p>
        </div>
      )}

      {!error && definitions.length > 0 && (
        <ul className="flex flex-col gap-2" role="list" aria-label="Workflow definitions">
          {definitions.map((definition) => (
            <li key={definition.id} role="listitem" className="flex items-start justify-between gap-3 rounded-lg border border-border/60 bg-card/30 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{definition.name}</span>
                  <code className="text-[10px]">{definition.id}</code>
                  <span>v{definition.version}</span>
                  {definition.tags.map((tag) => <span key={tag} className="rounded-full bg-violet-500/15 px-2 py-0.5 text-violet-300">{tag}</span>)}
                </div>
              </div>
              <div className="flex shrink-0 gap-1">
                <button type="button" onClick={() => void onRun(definition.id)} disabled={pending === definition.id}
                  aria-label={`Run workflow ${definition.id}`}
                  className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-emerald-400/40 hover:text-emerald-400 disabled:opacity-50">
                  {pending === definition.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                </button>
                {canAuthor && <button type="button" onClick={() => void onDelete(definition.id)} disabled={pending === definition.id}
                  aria-label={`Delete workflow definition ${definition.id}`}
                  className="rounded-md border border-border/60 p-1.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:opacity-50">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>}
              </div>
            </li>
          ))}
        </ul>
      )}

      <div>
        <h2 className="text-sm font-semibold text-muted-foreground">Recent runs</h2>
        {runs.length === 0
          ? <p className="mt-2 text-xs text-muted-foreground">No runs yet.</p>
          : <ul className="mt-2 flex flex-col gap-2" role="list" aria-label="Workflow runs">
            {runs.map((run) => (
              <li key={run.runId} role="listitem" className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-card/20 p-3 text-xs">
                <div className="min-w-0 flex-1">
                  <span className="font-mono">{run.runId}</span>
                  <span className="mx-2 text-muted-foreground">·</span>
                  <span className="text-muted-foreground">{run.workflowId}</span>
                  <span className="ml-2 rounded-full bg-muted px-2 py-0.5">{run.status}</span>
                  {run.error && <p className="mt-1 text-destructive">{run.error}</p>}
                </div>
                {(run.status === "running" || run.status === "pending") && (
                  <button type="button" onClick={() => void onCancel(run.runId)} disabled={pending === run.runId}
                    aria-label={`Cancel run ${run.runId}`} className="rounded-md border border-border/60 px-2 py-1 disabled:opacity-50">
                    Cancel</button>
                )}
              </li>
            ))}
          </ul>}
      </div>
    </section>
  );
}
