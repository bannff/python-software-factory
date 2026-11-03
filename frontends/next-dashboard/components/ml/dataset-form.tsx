"use client";

import type { DatasetInput } from "./datasets-api";
import type { DatasetFormErrors } from "./dataset-validation";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";
const FIELDS: [keyof DatasetInput, string][] = [
  ["name", "Name"], ["uri", "URI"], ["manifest_uri", "Manifest URI"], ["digest", "Digest"],
  ["view_name", "View name"], ["view_schema_version", "View schema version"], ["description", "Description"],
];

export function DatasetForm({ form, errors, busy, onChange, onSave, onCancel }: {
  form: DatasetInput; errors: DatasetFormErrors; busy: boolean;
  onChange: (next: DatasetInput) => void; onSave: () => void; onCancel: () => void;
}) {
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSave(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
      {errors.form && <p role="alert" className="text-xs text-destructive">{errors.form}</p>}
      {FIELDS.map(([key, label]) => (
        <label key={key} className="grid gap-1 text-xs"><span>{label}</span>
          <input aria-label={label} className={FIELD} value={form[key]} onChange={(e) => onChange({ ...form, [key]: e.target.value })}
            placeholder={key === "digest" ? "sha256:…" : undefined} />
          {errors[key] && <span role="alert" className="text-[11px] text-destructive">{errors[key]}</span>}
        </label>
      ))}
      <div className="flex items-center gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Save dataset</button>
        <button type="button" onClick={onCancel} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
      </div>
    </form>
  );
}
