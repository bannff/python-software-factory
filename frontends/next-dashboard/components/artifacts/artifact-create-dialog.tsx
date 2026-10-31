"use client";

import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
import { saveArtifact } from "./artifact-actions";
import type { Artifact, ArtifactKind } from "./artifact-types";

const KINDS: { value: ArtifactKind; label: string }[] = [
  { value: "markdown", label: "Markdown document" },
  { value: "text", label: "Plain text" },
  { value: "json", label: "JSON" },
  { value: "html", label: "HTML" },
];

/**
 * Row 63 / P1 item 10 (owner smoke #2): Artifacts had no create control at
 * all — list-only. This is the "+ New artifact" path: name, kind, content,
 * upload-from-file, saved via the real artifacts_save MCP tool.
 */
export function ArtifactCreateDialog({
  onCreated, onClose,
}: { onCreated: (artifact: Artifact) => void; onClose: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ArtifactKind>("markdown");
  const [content, setContent] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onFile = async (file: File) => {
    setContent(await file.text());
    if (!name.trim()) setName(file.name.replace(/\.[^.]+$/, ""));
  };

  const create = async () => {
    if (!name.trim() || !content.trim()) return;
    setBusy(true); setError(null);
    try {
      const artifact = await saveArtifact({ name: name.trim(), content, kind, description });
      onCreated(artifact);
    } catch {
      setError("Could not save this artifact. Check the name and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div role="dialog" aria-labelledby="new-artifact-title" className="rounded-xl border border-violet-500/30 bg-violet-500/[0.04] p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 id="new-artifact-title" className="font-medium">New artifact</h2>
        <button type="button" aria-label="Cancel new artifact" onClick={onClose} className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>
      <div className="grid gap-3">
        <label className="grid gap-1 text-xs">
          <span className="font-medium text-foreground/80">Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Design notes" className="rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-sm outline-none focus:border-violet-500/50" />
        </label>
        <label className="grid gap-1 text-xs">
          <span className="font-medium text-foreground/80">Kind</span>
          <select value={kind} onChange={(event) => setKind(event.target.value as ArtifactKind)} className="rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-sm outline-none focus:border-violet-500/50">
            {KINDS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs">
          <span className="font-medium text-foreground/80">Description (optional)</span>
          <input value={description} onChange={(event) => setDescription(event.target.value)} className="rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-sm outline-none focus:border-violet-500/50" />
        </label>
        <label className="grid gap-1 text-xs">
          <span className="flex items-center justify-between font-medium text-foreground/80">
            <span>Content</span>
            <span className="cursor-pointer font-normal text-violet-400 hover:text-violet-300">
              Upload a file
              <input type="file" aria-label="Upload artifact file" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void onFile(file); }} />
            </span>
          </span>
          <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={8} placeholder="Paste or type the artifact content…" className="rounded-lg border border-border/60 bg-background/60 px-3 py-2 font-mono text-xs outline-none focus:border-violet-500/50" />
        </label>
      </div>
      {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="rounded-lg border border-border/60 px-3 py-2 text-xs hover:bg-muted/50">Cancel</button>
        <button type="button" onClick={create} disabled={!name.trim() || !content.trim() || busy} className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} Create artifact
        </button>
      </div>
    </div>
  );
}
