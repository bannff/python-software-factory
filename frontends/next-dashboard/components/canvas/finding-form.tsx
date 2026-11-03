"use client";

import { useState } from "react";
import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { notifyFindingsChanged } from "@/lib/hooks/use-findings";
import { unwrapToolData } from "@/lib/tool-result-data";
import { SEV_ORDER } from "./findings-view-style";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";

/** Record a finding of any kind by hand. */
export function FindingForm({ kinds, onDone }: { kinds: string[]; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [kind, setKind] = useState("other");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!title.trim()) { setError("Enter a title."); return; }
    setBusy(true); setError(null);
    try {
      unwrapToolData(await callTool("graph_record_finding", { title: title.trim(), severity, kind: kind.trim() || "other", description }));
      notifyFindingsChanged(); onDone();
    } catch (cause) { setError(withReason("Finding could not be saved.", errorReason(cause))); }
    finally { setBusy(false); }
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); void save(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      <label className="grid gap-1 text-xs"><span>Title</span>
        <input aria-label="Title" className={FIELD} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <div className="grid grid-cols-2 gap-3">
        <label className="grid gap-1 text-xs"><span>Severity</span>
          <select aria-label="Severity" className={FIELD} value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {SEV_ORDER.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
        <label className="grid gap-1 text-xs"><span>Kind</span>
          <input aria-label="Kind" list="finding-kinds" className={FIELD} value={kind} onChange={(e) => setKind(e.target.value)} />
          <datalist id="finding-kinds">{kinds.map((k) => <option key={k} value={k} />)}</datalist></label>
      </div>
      <label className="grid gap-1 text-xs"><span>Description</span>
        <textarea aria-label="Description" className={`${FIELD} min-h-20`} value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      <div className="flex items-center gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Save finding</button>
        <button type="button" onClick={onDone} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
      </div>
    </form>
  );
}
