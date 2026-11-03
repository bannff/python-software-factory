"use client";

import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, ScrollText, Trash2 } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { errorReason, withReason } from "@/lib/error-reason";
import { useMounted } from "@/lib/hooks/use-mounted";
import {
  addPrompt, deletePrompt, listAuthoredPrompts, updatePrompt, type AuthoredPrompt,
} from "./authored-prompts-api";
import { PromptEditor } from "./prompt-editor";
import { serverFieldError, validatePromptForm, type PromptFormErrors, type PromptFormValues } from "./prompt-validation";

const BLANK: PromptFormValues = { prompt_id: "", description: "", template: "", args: [] };

/** Prompts the owner wrote; the built-in registry prompts below stay read-only. */
export function AuthoredPromptsPanel() {
  const [prompts, setPrompts] = useState<AuthoredPrompt[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState<{ form: PromptFormValues; revision: number | null } | null>(null);
  const [errors, setErrors] = useState<PromptFormErrors>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const mounted = useMounted();

  const refresh = useCallback(async () => {
    try {
      const next = await listAuthoredPrompts();
      if (!mounted.current) return;
      setPrompts(next); setNotice(null);
    } catch (cause) {
      if (mounted.current) setNotice(withReason("Your prompts are unavailable.", errorReason(cause)));
    } finally { if (mounted.current) setLoaded(true); }
  }, [mounted]);
  useEffect(() => { void refresh(); }, [refresh]);

  const save = async () => {
    if (!editing) return;
    const creating = editing.revision === null;
    const found = validatePromptForm(editing.form, creating);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    const input = { prompt_id: editing.form.prompt_id, description: editing.form.description,
      template: editing.form.template, arguments: editing.form.args };
    setBusy(true);
    try {
      if (creating) await addPrompt(input); else await updatePrompt(input, editing.revision as number);
      setEditing(null); await refresh();
    } catch (cause) {
      const reason = errorReason(cause);
      setErrors(serverFieldError(reason) ?? { form: withReason("Prompt could not be saved.", reason) });
    } finally { setBusy(false); }
  };
  const remove = async (id: string) => {
    try { await deletePrompt(id); await refresh(); }
    catch (cause) { setNotice(withReason("Prompt could not be removed.", errorReason(cause))); }
  };
  const open = (form: PromptFormValues, revision: number | null) => { setErrors({}); setEditing({ form, revision }); };

  return (
    <section aria-label="Your prompts" className="mb-6 grid gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Your prompts</h3>
        {!editing && <button type="button" aria-label="New prompt" onClick={() => open(BLANK, null)}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> New prompt</button>}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {editing && <PromptEditor form={editing.form} errors={errors} creating={editing.revision === null} busy={busy}
        onChange={(form) => setEditing({ ...editing, form })} onSave={() => void save()} onCancel={() => setEditing(null)} />}
      {loaded && prompts.length === 0 && !editing && !notice && (
        <EmptyState icon={ScrollText} title="No prompts of your own yet" hint="Write one to reuse it in any chat." />
      )}
      {prompts.map((p) => (
        <div key={p.prompt_id} className="flex items-center gap-3 rounded-xl border border-border/60 bg-card/20 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-sm font-semibold">{p.prompt_id}</p>
            <p className="truncate text-xs text-muted-foreground">{p.description || "No description provided."}</p>
          </div>
          <button type="button" aria-label={`Edit prompt ${p.prompt_id}`} className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
            onClick={() => open({ prompt_id: p.prompt_id, description: p.description, template: p.template, args: p.arguments }, p.revision)}>
            <Pencil className="h-3.5 w-3.5" /></button>
          <ConfirmDelete label={`Delete prompt ${p.prompt_id}`} onConfirm={() => void remove(p.prompt_id)}
            className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></ConfirmDelete>
        </div>
      ))}
    </section>
  );
}
