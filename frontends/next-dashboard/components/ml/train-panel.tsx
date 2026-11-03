"use client";

import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { useMounted } from "@/lib/hooks/use-mounted";
import { listDatasets, type Dataset } from "./datasets-api";
import { listModelTypes, trainFailure, trainModel, type TrainResult } from "./train-api";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";
const BLANK = { model_type: "", X_uri: "", y_uri: "", experiment_name: "" };

/** Train a time-series model from two dataset locations; the run then shows up under Experiments. */
export function TrainPanel() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(BLANK);
  const [types, setTypes] = useState<string[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TrainResult | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useMounted();

  useEffect(() => {
    if (!open) return;
    void listModelTypes().then((t) => { if (mounted.current) { setTypes(t); setForm((f) => ({ ...f, model_type: f.model_type || t[0] || "" })); } }).catch(() => undefined);
    void listDatasets().then((d) => { if (mounted.current) setDatasets(d); }).catch(() => undefined);
  }, [open, mounted]);

  const start = async () => {
    if (!form.model_type.trim()) { setError("Choose a model type."); return; }
    if (!form.X_uri.trim() || !form.y_uri.trim()) { setError("Enter both the features location (X) and the labels location (y)."); return; }
    setBusy(true); setError(null); setResult(null);
    try { const r = await trainModel({ ...form, experiment_name: form.experiment_name.trim() }); if (mounted.current) { setResult(r); setOpen(false); } }
    catch (cause) { if (mounted.current) setError(trainFailure(cause)); }
    finally { if (mounted.current) setBusy(false); }
  };
  const set = (patch: Partial<typeof BLANK>) => setForm({ ...form, ...patch });

  return (
    <section aria-label="Train a model" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Train a model</h3>
        {!open && <button type="button" aria-label="Train a model" onClick={() => { setError(null); setOpen(true); }}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Cpu className="h-3.5 w-3.5" aria-hidden /> Train a model</button>}
      </div>
      {result && (
        <p role="status" className="text-xs text-emerald-400">
          Training {result.status || "finished"} · job {result.job_id}
          {Object.entries(result.metrics).slice(0, 3).map(([k, v]) => ` · ${k} ${typeof v === "number" ? v.toFixed(3) : v}`).join("")}
          . Use the refresh icon to see it under Experiments.
        </p>
      )}
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {open && (
        <form onSubmit={(e) => { e.preventDefault(); void start(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
          <label className="grid gap-1 text-xs"><span>Model type</span>
            {types.length > 0 ? (
              <select aria-label="Model type" className={FIELD} value={form.model_type} onChange={(e) => set({ model_type: e.target.value })}>
                {types.map((t) => <option key={t} value={t}>{t}</option>)}</select>
            ) : (
              <input aria-label="Model type" className={FIELD} value={form.model_type} onChange={(e) => set({ model_type: e.target.value })} />
            )}</label>
          <label className="grid gap-1 text-xs"><span>Features (X)</span>
            <input aria-label="Features (X)" list="train-datasets" className={FIELD} value={form.X_uri} onChange={(e) => set({ X_uri: e.target.value })} />
            <span className="text-[11px] text-muted-foreground">Where the windowed feature array lives (a file or URI the server can read).</span></label>
          <label className="grid gap-1 text-xs"><span>Labels (y)</span>
            <input aria-label="Labels (y)" list="train-datasets" className={FIELD} value={form.y_uri} onChange={(e) => set({ y_uri: e.target.value })} />
            <span className="text-[11px] text-muted-foreground">Where the labels live: one label per window of X.</span></label>
          <datalist id="train-datasets">{datasets.map((d) => <option key={d.dataset_id} value={d.uri}>{d.dataset_id}</option>)}</datalist>
          <label className="grid gap-1 text-xs"><span>Experiment name</span>
            <input aria-label="Experiment name" className={FIELD} value={form.experiment_name} onChange={(e) => set({ experiment_name: e.target.value })} placeholder="Optional" /></label>
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">{busy ? "Training…" : "Start training"}</button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
          </div>
        </form>
      )}
    </section>
  );
}
