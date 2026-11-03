"use client";

import type { FineTuneMethod, JobInput } from "./finetune-api";
import type { Dataset } from "./datasets-api";
import type { BaseModel } from "./base-models-api";
import type { JobFormErrors } from "./finetune-validation";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";
const TEXT: [keyof JobInput, string][] = [
  ["dataset_uri", "Dataset URI"], ["manifest_uri", "Manifest URI"],
  ["dataset_digest", "Dataset digest"], ["view_name", "View name"], ["view_schema_version", "View schema version"],
];

export function FineTuneForm({ form, errors, methods, datasets, baseModels, busy, onChange, onSave, onCancel }: {
  form: JobInput; errors: JobFormErrors; methods: FineTuneMethod[]; datasets: Dataset[]; baseModels: BaseModel[]; busy: boolean;
  onChange: (next: JobInput) => void; onSave: () => void; onCancel: () => void;
}) {
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSave(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
      <label className="grid gap-1 text-xs"><span>Method</span>
        <select aria-label="Method" className={FIELD} value={form.method} onChange={(e) => onChange({ ...form, method: e.target.value })}>
          {methods.map((m) => <option key={m.name} value={m.name} title={m.description}>{m.name}</option>)}
        </select>
        {errors.method && <span role="alert" className="text-[11px] text-destructive">{errors.method}</span>}
      </label>
      <label className="grid gap-1 text-xs"><span>Base model</span>
        {baseModels.length > 0 ? (
          <select aria-label="Base model" className={FIELD} value={form.base_model} onChange={(e) => onChange({ ...form, base_model: e.target.value })}>
            <option value="">Choose…</option>
            {baseModels.map((b) => <option key={b.name} value={b.model_id} title={b.model_id}>{b.name}</option>)}
          </select>
        ) : (
          <input aria-label="Base model" className={FIELD} value={form.base_model} onChange={(e) => onChange({ ...form, base_model: e.target.value })} />
        )}
        {errors.base_model && <span role="alert" className="text-[11px] text-destructive">{errors.base_model}</span>}
      </label>
      {datasets.length > 0 && (
        <label className="grid gap-1 text-xs"><span>Dataset</span>
          <select aria-label="Dataset" className={FIELD} value={form.dataset_id ?? ""} onChange={(e) => onChange({ ...form, dataset_id: e.target.value })}>
            <option value="">Enter details manually</option>
            {datasets.map((d) => <option key={d.dataset_id} value={d.dataset_id}>{d.dataset_id}</option>)}
          </select>
        </label>
      )}
      {!form.dataset_id && TEXT.map(([key, label]) => (
        <label key={key} className="grid gap-1 text-xs"><span>{label}</span>
          <input aria-label={label} className={FIELD} value={form[key] ?? ""} onChange={(e) => onChange({ ...form, [key]: e.target.value })} />
          {errors[key] && <span role="alert" className="text-[11px] text-destructive">{errors[key]}</span>}
        </label>
      ))}
      <div className="flex items-center gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Create job</button>
        <button type="button" onClick={onCancel} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
      </div>
    </form>
  );
}
