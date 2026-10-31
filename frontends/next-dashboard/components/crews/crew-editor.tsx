"use client";

import { useState } from "react";
import { Loader2, Star } from "lucide-react";
import { callTool } from "@/lib/api";
import { usePersonas } from "@/lib/hooks/use-personas";
import { useModelCatalog } from "@/lib/hooks/use-model-catalog";
import { CREW_FORM_HINT } from "./crew-field-hints";
import { Field, InfoHint, FIELD } from "./crew-field";
import type { Crew } from "./crew-types";

/**
 * Focused create/edit panel (NOT a master-detail/table redesign). A new
 * Crew starts blank; an existing Crew hydrates its fields and exposes a
 * revision-fenced Save plus a Set-as-default action. Mutations go through
 * the real typed MCP tools; stale-revision conflicts surface truthfully.
 */
export function CrewEditor({ crew, isDefault, onSaved, onClose }: {
  crew: Crew | null; isDefault: boolean; onSaved: () => void; onClose: () => void;
}) {
  const creating = crew === null;
  const { personas } = usePersonas();
  const { groups, error: catalogError } = useModelCatalog({ scope: "all" });
  const [form, setForm] = useState({
    id: crew?.id ?? "", name: crew?.name ?? "", persona_id: crew?.persona_id ?? "",
    project: crew?.project ?? "", memory_scope: crew?.memory_scope ?? "",
    model: crew?.model ?? "", description: crew?.description ?? "",
    workspace: crew?.workspace ?? "", triggers: (crew?.triggers ?? []).join(", "),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof typeof form) => (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const save = async () => {
    setSaving(true);
    setError(null);
    const triggers = form.triggers.split(",").map((t) => t.trim()).filter(Boolean);
    const base = {
      crew_id: form.id, name: form.name, persona_id: form.persona_id,
      project: form.project, memory_scope: form.memory_scope,
      description: form.description, workspace: form.workspace,
      model: form.model, triggers,
    };
    try {
      if (creating) await callTool("agent_create_crew", base);
      else await callTool("agent_update_crew", { ...base, expected_revision: crew.revision });
      onSaved();
      onClose();
    } catch {
      setError(creating
        ? "Couldn’t create this crew. Check the fields and try again."
        : "Couldn’t save — this crew may have changed. Reopen it and retry.");
    } finally {
      setSaving(false);
    }
  };

  const setDefault = async () => {
    if (!crew) return;
    setSaving(true);
    setError(null);
    try {
      await callTool("agent_set_default_crew", { crew_id: crew.id, expected_revision: crew.revision });
      onSaved();
      onClose();
    } catch {
      setError("Couldn’t set default — this crew may have changed. Reopen it and retry.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="rounded-xl border border-violet-500/30 bg-violet-500/[0.04] p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-1.5 font-medium">
          {creating ? "New crew" : `Edit ${crew.name}`}
          <InfoHint id="crew-form-hint" label="crew" hint={CREW_FORM_HINT} />
        </h2>
        <button type="button" onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">Close</button>
      </div>
      {error && <div role="alert" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">{error}</div>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field field="id">
          <input className={FIELD} value={form.id} onChange={set("id")} disabled={!creating}
            placeholder="redteam-crew" />
        </Field>
        <Field field="name">
          <input className={FIELD} value={form.name} onChange={set("name")} placeholder="Red Team" />
        </Field>
        <Field field="persona_id">
          <select className={FIELD} value={form.persona_id} onChange={set("persona_id")}>
            <option value="">Select a persona…</option>
            {personas.map((p) => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
          </select>
        </Field>
        <Field field="model" note={catalogError ? (
          <span className="text-[10px] text-muted-foreground/70">Model catalog unavailable — Inherit is safe; other options can’t load right now.</span>
        ) : null}>
          <select className={FIELD} value={form.model} onChange={set("model")}>
            <option value="">Inherit (persona / default)</option>
            {groups.map((group) => (
              <optgroup key={group.provider} label={group.provider}>
                {group.models.map((m) => <option key={m.model_id} value={m.model_id}>{m.model}</option>)}
              </optgroup>
            ))}
          </select>
        </Field>
        <Field field="project">
          <input className={FIELD} value={form.project} onChange={set("project")} placeholder="/abs/path/to/project" />
        </Field>
        <Field field="memory_scope">
          <input className={FIELD} value={form.memory_scope} onChange={set("memory_scope")} placeholder="redteam" />
        </Field>
        <Field field="description" className="sm:col-span-2">
          <textarea className={FIELD} value={form.description} onChange={set("description")} rows={2} />
        </Field>
        <Field field="triggers" className="sm:col-span-2">
          <input className={FIELD} value={form.triggers} onChange={set("triggers")} placeholder="scan, audit" />
        </Field>
      </div>
      <div className="mt-4 flex items-center gap-2">
        <button type="button" onClick={save} disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-md bg-violet-500/90 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:opacity-60">
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {creating ? "Create crew" : "Save changes"}
        </button>
        {!creating && !isDefault && (
          <button type="button" onClick={setDefault} disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground disabled:opacity-60">
            <Star className="h-3.5 w-3.5" /> Set as default
          </button>
        )}
      </div>
    </article>
  );
}
