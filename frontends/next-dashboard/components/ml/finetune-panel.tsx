"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, Play, Plus, Square, Trash2 } from "lucide-react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { EmptyState } from "@/components/ui/empty-state";
import { errorReason, withReason } from "@/lib/error-reason";
import { createJob, deleteJob, jobFailure, listJobs, listMethods, startJob, stopJob, type FineTuneJob, type FineTuneMethod, type JobInput } from "./finetune-api";
import { listBaseModels, type BaseModel } from "./base-models-api";
import { listDatasets, type Dataset } from "./datasets-api";
import { FineTuneForm } from "./finetune-form";
import { validateJobForm, type JobFormErrors } from "./finetune-validation";

const BLANK: JobInput = { method: "", base_model: "", dataset_uri: "", manifest_uri: "", dataset_digest: "", view_name: "", view_schema_version: "" };
const RUNNING = new Set(["running", "checkpointing"]);

/** Fine-tuning jobs: list, create, start and stop, driven by the ml_* job tools. */
export function FineTunePanel() {
  const [jobs, setJobs] = useState<FineTuneJob[]>([]);
  const [methods, setMethods] = useState<FineTuneMethod[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [baseModels, setBaseModels] = useState<BaseModel[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [form, setForm] = useState<JobInput | null>(null);
  const [errors, setErrors] = useState<JobFormErrors>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try { setJobs(await listJobs()); setNotice(null); }
    catch (cause) { setNotice(withReason("Fine-tuning jobs are unavailable.", errorReason(cause))); }
    finally { setLoaded(true); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const open = async () => {
    setErrors({});
    let available = methods;
    if (available.length === 0) {
      try { available = await listMethods(); setMethods(available); }
      catch (cause) { setNotice(withReason("Fine-tuning methods are unavailable.", errorReason(cause))); return; }
    }
    setDatasets(await listDatasets().catch(() => []));
    setBaseModels(await listBaseModels().catch(() => []));
    setForm({ ...BLANK, method: available[0]?.name ?? "" });
  };
  const run = async (action: () => Promise<void>, failure: string) => {
    setBusy(true);
    try { await action(); await refresh(); return true; }
    catch (cause) { setNotice(jobFailure(failure, cause)); return false; }
    finally { setBusy(false); }
  };
  const save = async () => {
    if (!form) return;
    const found = validateJobForm(form);
    setErrors(found);
    if (Object.keys(found).length === 0 && await run(() => createJob(form), "Job could not be created.")) setForm(null);
  };

  return (
    <section aria-label="Fine-tuning jobs" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Fine-tuning jobs</h3>
        {!form && <button type="button" onClick={() => void open()}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> New job</button>}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {form && <FineTuneForm form={form} errors={errors} methods={methods} datasets={datasets} baseModels={baseModels} busy={busy}
        onChange={setForm} onSave={() => void save()} onCancel={() => setForm(null)} />}
      {loaded && jobs.length === 0 && !form && !notice && (
        <EmptyState icon={Brain} title="No fine-tuning jobs yet" hint="Create one from a dataset to adapt a base model." />
      )}
      {jobs.map((j) => (
        <div key={j.id} className="flex items-center gap-3 rounded-xl border border-border/60 bg-card/20 px-4 py-3">
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-sm font-semibold">{j.id}</p>
            <p className="truncate text-xs text-muted-foreground">
              {[j.status, j.method, j.base_model, j.loss !== null ? `loss ${j.loss.toFixed(3)}` : ""].filter(Boolean).join(" · ")}
            </p>
          </div>
          {j.status === "pending" && <button type="button" aria-label={`Start job ${j.id}`} disabled={busy}
            onClick={() => void run(() => startJob(j.id), "Job could not be started.")}
            className="rounded-md p-1.5 text-muted-foreground hover:text-foreground"><Play className="h-3.5 w-3.5" /></button>}
          {!RUNNING.has(j.status) && <ConfirmDelete label={`Delete job ${j.id}`} disabled={busy}
            onConfirm={() => void run(() => deleteJob(j.id), "Job could not be deleted.")}
            className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><Trash2 className="h-3.5 w-3.5" /></ConfirmDelete>}
          {RUNNING.has(j.status) && <button type="button" aria-label={`Stop job ${j.id}`} disabled={busy}
            onClick={() => void run(() => stopJob(j.id), "Job could not be stopped.")}
            className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><Square className="h-3.5 w-3.5" /></button>}
        </div>
      ))}
    </section>
  );
}
