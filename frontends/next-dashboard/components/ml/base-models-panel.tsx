"use client";

import { useCallback, useEffect, useState } from "react";
import { Boxes, Pencil, Plus, Trash2 } from "lucide-react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { EmptyState } from "@/components/ui/empty-state";
import { useMounted } from "@/lib/hooks/use-mounted";
import {
  baseModelFailure, deleteBaseModel, listBaseModels, registerBaseModel, updateBaseModel, type BaseModel,
} from "./base-models-api";
import { listMethods, type FineTuneMethod } from "./finetune-api";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";
const BLANK: BaseModel = { name: "", model_id: "", description: "", recommended_method: "" };

/** Base models a fine-tuning job can start from: register, edit, delete. */
export function BaseModelsPanel() {
  const [models, setModels] = useState<BaseModel[]>([]);
  const [methods, setMethods] = useState<FineTuneMethod[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [form, setForm] = useState<{ value: BaseModel; editing: boolean } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useMounted();

  const refresh = useCallback(async () => {
    try {
      const next = await listBaseModels();
      if (mounted.current) setModels(next);
    } catch (cause) { if (mounted.current) setNotice(baseModelFailure("Base models are unavailable.", cause)); }
    finally { if (mounted.current) setLoaded(true); }
  }, [mounted]);
  useEffect(() => { void refresh(); }, [refresh]);

  const open = async (value: BaseModel, editing: boolean) => {
    setNotice(null);
    try {
      const available = methods.length > 0 ? methods : await listMethods();
      setMethods(available);
      setForm({ value: { ...value, recommended_method: value.recommended_method || available[0]?.name || "" }, editing });
    } catch (cause) { setNotice(baseModelFailure("Fine-tuning methods are unavailable.", cause)); }
  };
  const run = async (action: () => Promise<void>, failure: string) => {
    setBusy(true); setNotice(null);
    try { await action(); setForm(null); await refresh(); }
    catch (cause) { setNotice(baseModelFailure(failure, cause)); }
    finally { setBusy(false); }
  };
  const save = () => {
    if (!form) return;
    const v = form.value;
    if (!v.name.trim() || !v.model_id.trim()) { setNotice("Enter a name and a model ID."); return; }
    void run(() => (form.editing ? updateBaseModel(v) : registerBaseModel(v)), "Base model could not be saved.");
  };
  const set = (patch: Partial<BaseModel>) => form && setForm({ ...form, value: { ...form.value, ...patch } });

  return (
    <section aria-label="Base models" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Base models</h3>
        {!form && <button type="button" aria-label="Register base model" onClick={() => void open(BLANK, false)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> Register base model</button>}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {form && (
        <form onSubmit={(e) => { e.preventDefault(); save(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
          <label className="grid gap-1 text-xs"><span>Name</span>
            <input aria-label="Name" className={FIELD} value={form.value.name} disabled={form.editing} onChange={(e) => set({ name: e.target.value })} /></label>
          <label className="grid gap-1 text-xs"><span>Model ID</span>
            <input aria-label="Model ID" className={FIELD} value={form.value.model_id} onChange={(e) => set({ model_id: e.target.value })} /></label>
          <label className="grid gap-1 text-xs"><span>Description</span>
            <input aria-label="Description" className={FIELD} value={form.value.description} onChange={(e) => set({ description: e.target.value })} /></label>
          <label className="grid gap-1 text-xs"><span>Recommended method</span>
            <select aria-label="Recommended method" className={FIELD} value={form.value.recommended_method} onChange={(e) => set({ recommended_method: e.target.value })}>
              {methods.map((m) => <option key={m.name} value={m.name}>{m.name}</option>)}</select></label>
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Save base model</button>
            <button type="button" onClick={() => setForm(null)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
          </div>
        </form>
      )}
      {loaded && models.length === 0 && !form && !notice && (
        <EmptyState icon={Boxes} title="No base models registered yet" hint="Register one to start fine-tuning jobs from a list." />
      )}
      {models.map((m) => (
        <div key={m.name} className="flex items-center gap-3 rounded-xl border border-border/60 bg-card/20 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-sm font-semibold">{m.name}</p>
            <p className="truncate text-xs text-muted-foreground">{[m.model_id, m.recommended_method, m.description].filter(Boolean).join(" · ")}</p>
          </div>
          <button type="button" aria-label={`Edit base model ${m.name}`} className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
            onClick={() => void open(m, true)}><Pencil className="h-3.5 w-3.5" /></button>
          <ConfirmDelete label={`Delete base model ${m.name}`} disabled={busy} onConfirm={() => void run(() => deleteBaseModel(m.name), "Base model could not be removed.")}
            className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></ConfirmDelete>
        </div>
      ))}
    </section>
  );
}
