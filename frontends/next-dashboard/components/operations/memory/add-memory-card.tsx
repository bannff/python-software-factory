"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { useMounted } from "@/lib/hooks/use-mounted";
import { unwrapToolData } from "@/lib/tool-result-data";
import type { MemoryType } from "./memory-types";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";
const TYPES: [MemoryType, string][] = [["short_term", "Short-term"], ["long_term", "Long-term"], ["episodic", "Episodic"]];

/** Teach Companion X something by hand; the new memory then shows in the list. */
export default function AddMemoryCard({ onSaved }: { onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [type, setType] = useState<MemoryType>("short_term");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useMounted();

  const save = async () => {
    if (!content.trim()) { setError("Enter what Companion X should remember."); return; }
    setBusy(true); setError(null);
    try {
      const data = unwrapToolData(await callTool("memory_store", { content: content.trim(), memory_type: type })) as { stored?: boolean; error?: string } | null;
      if (data?.stored === false) { if (mounted.current) setError(withReason("The memory could not be saved.", data.error)); return; }
      if (mounted.current) { setContent(""); setOpen(false); }
      onSaved();
    } catch (cause) { if (mounted.current) setError(withReason("The memory could not be saved.", errorReason(cause))); }
    finally { if (mounted.current) setBusy(false); }
  };

  if (!open) {
    return (
      <div className="flex items-center justify-between">
        {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
        <button type="button" aria-label="Add a memory" onClick={() => { setError(null); setOpen(true); }}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> Add a memory</button>
      </div>
    );
  }
  return (
    <form onSubmit={(e) => { e.preventDefault(); void save(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      <label className="grid gap-1 text-xs"><span>Memory</span>
        <textarea aria-label="Memory" className={`${FIELD} min-h-16`} value={content} onChange={(e) => setContent(e.target.value)} placeholder="e.g. I prefer concise answers" /></label>
      <label className="grid gap-1 text-xs"><span>Type</span>
        <select aria-label="Type" className={FIELD} value={type} onChange={(e) => setType(e.target.value as MemoryType)}>
          {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">{busy ? "Saving…" : "Save memory"}</button>
        <button type="button" onClick={() => setOpen(false)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
      </div>
    </form>
  );
}
