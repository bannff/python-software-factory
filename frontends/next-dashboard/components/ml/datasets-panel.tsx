"use client";

import { useCallback, useEffect, useState } from "react";
import { Database, Pencil, Plus, Trash2 } from "lucide-react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { EmptyState } from "@/components/ui/empty-state";
import { errorReason, withReason } from "@/lib/error-reason";
import { deleteDataset, listDatasets, registerDataset, updateDataset, type Dataset, type DatasetInput } from "./datasets-api";
import { DatasetForm } from "./dataset-form";
import { serverDatasetError, validateDatasetForm, type DatasetFormErrors } from "./dataset-validation";

const BLANK: DatasetInput = { name: "", uri: "", manifest_uri: "", digest: "", view_name: "", view_schema_version: "", description: "" };

/** Registered training datasets: register, edit the description, delete. */
export function DatasetsPanel() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [form, setForm] = useState<DatasetInput | null>(null);
  const [errors, setErrors] = useState<DatasetFormErrors>({});
  const [editing, setEditing] = useState<{ id: string; description: string; revision: number } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try { setDatasets(await listDatasets()); setNotice(null); }
    catch (cause) { setNotice(withReason("Datasets are unavailable.", errorReason(cause))); }
    finally { setLoaded(true); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const save = async () => {
    if (!form) return;
    const found = validateDatasetForm(form);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    try { await registerDataset(form); setForm(null); await refresh(); }
    catch (cause) {
      const reason = errorReason(cause);
      setErrors(serverDatasetError(reason) ?? { form: withReason("Dataset could not be saved.", reason) });
    } finally { setBusy(false); }
  };
  const saveDescription = async () => {
    if (!editing) return;
    try { await updateDataset(editing.id, editing.description, editing.revision); setEditing(null); await refresh(); }
    catch (cause) {
      const reason = errorReason(cause);
      setNotice(serverDatasetError(reason)?.form ?? withReason("Description could not be saved.", reason));
    }
  };
  const remove = async (id: string) => {
    try { await deleteDataset(id); await refresh(); }
    catch (cause) {
      const reason = errorReason(cause);
      setNotice(reason?.includes("dataset_in_use")
        ? "This dataset is used by a fine-tuning job. Delete that job first."
        : withReason("Dataset could not be removed.", reason));
    }
  };

  return (
    <section aria-label="Datasets" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Datasets</h3>
        {!form && <button type="button" aria-label="Register dataset" onClick={() => { setErrors({}); setForm(BLANK); }}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> Register dataset</button>}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {form && <DatasetForm form={form} errors={errors} busy={busy} onChange={setForm} onSave={() => void save()} onCancel={() => setForm(null)} />}
      {loaded && datasets.length === 0 && !form && !notice && (
        <EmptyState icon={Database} title="No datasets registered yet" hint="Register one to reuse it across fine-tuning jobs." />
      )}
      {datasets.map((d) => (
        <div key={d.dataset_id} className="flex items-center gap-3 rounded-xl border border-border/60 bg-card/20 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-sm font-semibold">{d.dataset_id}</p>
            {editing?.id === d.dataset_id ? (
              <div className="mt-1 flex items-center gap-2">
                <input aria-label="Description" className="w-full rounded-md border bg-background/50 px-2 py-1 text-xs" value={editing.description}
                  onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
                <button type="button" onClick={() => void saveDescription()} className="shrink-0 rounded-md bg-violet-500 px-2 py-1 text-[11px] text-white">Save description</button>
              </div>
            ) : (
              <p className="truncate text-xs text-muted-foreground">{[d.view_name, d.description].filter(Boolean).join(" · ") || d.uri}</p>
            )}
          </div>
          <button type="button" aria-label={`Edit dataset ${d.dataset_id}`} className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"
            onClick={() => setEditing({ id: d.dataset_id, description: d.description, revision: d.revision })}><Pencil className="h-3.5 w-3.5" /></button>
          <ConfirmDelete label={`Delete dataset ${d.dataset_id}`} onConfirm={() => void remove(d.dataset_id)}
            className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></ConfirmDelete>
        </div>
      ))}
    </section>
  );
}
