"use client";

import { Plus, Trash2 } from "lucide-react";
import type { PromptFormErrors, PromptFormValues } from "./prompt-validation";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return <label className="grid gap-1 text-xs"><span>{label}</span>{children}
    {error && <span role="alert" className="text-[11px] text-destructive">{error}</span>}</label>;
}

export function PromptEditor({ form, errors, creating, busy, onChange, onSave, onCancel }: {
  form: PromptFormValues; errors: PromptFormErrors; creating: boolean; busy: boolean;
  onChange: (next: PromptFormValues) => void; onSave: () => void; onCancel: () => void;
}) {
  const setArg = (i: number, patch: Partial<PromptFormValues["args"][number]>) =>
    onChange({ ...form, args: form.args.map((a, j) => (j === i ? { ...a, ...patch } : a)) });
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSave(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
      {errors.form && <p role="alert" className="text-xs text-destructive">{errors.form}</p>}
      <Field label="Prompt ID" error={errors.prompt_id}>
        <input className={FIELD} aria-label="Prompt ID" value={form.prompt_id} disabled={!creating}
          onChange={(e) => onChange({ ...form, prompt_id: e.target.value })} placeholder="triage-finding" />
      </Field>
      <Field label="Description" error={errors.description}>
        <input className={FIELD} aria-label="Description" value={form.description}
          onChange={(e) => onChange({ ...form, description: e.target.value })} />
      </Field>
      <Field label="Template (use {name} for each argument)" error={errors.template}>
        <textarea className={`${FIELD} min-h-32 font-mono`} aria-label="Template" value={form.template}
          onChange={(e) => onChange({ ...form, template: e.target.value })} placeholder="Review {finding} and propose a fix." />
      </Field>
      <div className="grid gap-2">
        <span className="text-xs">Arguments</span>
        {form.args.map((arg, i) => (
          <div key={i} className="flex items-center gap-2">
            <input className={FIELD} aria-label={`Argument ${i + 1} name`} value={arg.name} placeholder="name"
              onChange={(e) => setArg(i, { name: e.target.value })} />
            <label className="flex shrink-0 items-center gap-1 text-[11px]">
              <input type="checkbox" checked={arg.required} onChange={(e) => setArg(i, { required: e.target.checked })} /> required
            </label>
            <button type="button" aria-label={`Remove argument ${i + 1}`} className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
              onClick={() => onChange({ ...form, args: form.args.filter((_, j) => j !== i) })}><Trash2 className="h-3.5 w-3.5" /></button>
          </div>
        ))}
        {errors.args && <p role="alert" className="text-[11px] text-destructive">{errors.args}</p>}
        <button type="button" onClick={() => onChange({ ...form, args: [...form.args, { name: "", description: "", required: false }] })}
          className="inline-flex w-fit items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"><Plus className="h-3 w-3" /> Add argument</button>
      </div>
      <div className="flex items-center gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Save prompt</button>
        <button type="button" onClick={onCancel} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
      </div>
    </form>
  );
}
