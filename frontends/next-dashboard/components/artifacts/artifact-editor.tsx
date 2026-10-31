"use client";

import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import type { Artifact } from "./artifact-types";
import { STALE_ARTIFACT_MESSAGE, updateArtifact } from "./artifact-actions";

export function ArtifactEditor({
  artifact, onSaved,
}: { artifact: Artifact; onSaved: (artifact: Artifact) => void }) {
  const [content, setContent] = useState(artifact.content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setContent(artifact.content); }, [artifact.content, artifact.version]);

  const save = async () => {
    setSaving(true); setError(null);
    try { onSaved(await updateArtifact(artifact, content)); }
    catch { setError(STALE_ARTIFACT_MESSAGE); }
    finally { setSaving(false); }
  };

  return (
    <section aria-labelledby="artifact-editor-title" className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div><h3 id="artifact-editor-title" className="text-sm font-medium">Current content</h3><p className="text-xs text-muted-foreground">Revision {artifact.revision} · version {artifact.version}</p></div>
        <button type="button" onClick={save} disabled={saving || content === artifact.content} className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500/15 px-3 py-1.5 text-xs font-medium text-violet-300 transition-colors hover:bg-violet-500/25 disabled:opacity-40">
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save version
        </button>
      </div>
      <textarea aria-label="Artifact content" value={content} onChange={(event) => setContent(event.target.value)} className="min-h-52 w-full resize-y rounded-lg border border-border/60 bg-background/60 p-3 font-mono text-xs leading-5 outline-none focus:border-violet-500/50" />
      {error && <div role="alert" className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">{error}</div>}
    </section>
  );
}
