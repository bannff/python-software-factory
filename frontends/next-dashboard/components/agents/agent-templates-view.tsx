"use client";

import { useEffect, useState } from "react";
import { Loader2, Plus, Save, Trash2, GitFork, RotateCcw } from "lucide-react";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import { usePersonas } from "@/lib/hooks/use-personas";
import type { Persona } from "@/lib/types";
import { authoringGateNotice, getAuthoringCapabilities,
  type AuthoringCapabilities } from "@/lib/authoring-capabilities";
import {
  deleteUserTemplate, forkTemplate, listUserTemplateIds,
  readUserTemplate, resetTemplate, saveUserTemplate,
} from "./agent-template-api";

const EMPTY = { id: "", name: "", description: "", model: "", system_prompt: "" };
type Form = typeof EMPTY;

/** The capability probe is async; keep "unknown" distinct from "denied". */
type Capabilities =
  | { status: "checking" }
  | { status: "failed"; message: string }
  | { status: "ready"; caps: AuthoringCapabilities };

function fromPersona(persona: Persona): Form {
  return { id: persona.id, name: persona.name, description: persona.description,
    model: persona.model ?? "", system_prompt: "" };
}

export default function AgentTemplatesView() {
  const { personas, loading, error, refresh } = usePersonas();
  const { ready } = useMcpConnection();
  const [userIds, setUserIds] = useState<Set<string>>(new Set());
  const [capabilities, setCapabilities] = useState<Capabilities>({ status: "checking" });
  const [selected, setSelected] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [raw, setRaw] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    void getAuthoringCapabilities().then(async (caps) => {
      setCapabilities({ status: "ready", caps });
      if (caps.config.read) setUserIds(new Set(await listUserTemplateIds()));
    }).catch((cause) => {
      setCapabilities({ status: "failed",
        message: cause instanceof Error ? cause.message : "Couldn’t inspect Agent authoring capabilities." });
    });
  }, [personas.length, ready]);

  const choose = async (persona: Persona) => {
    setSelected(persona.id); setNotice(null); setForm(fromPersona(persona)); setRaw({});
    if (!userIds.has(persona.id)) return;
    setBusy(true);
    try {
      const config = await readUserTemplate(persona.id);
      setRaw(config);
      setForm({
        id: String(config.id ?? persona.id), name: String(config.name ?? persona.name),
        description: String(config.description ?? ""), model: String(config.model ?? ""),
        system_prompt: String(config.system_prompt ?? ""),
      });
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : "Template unavailable."); }
    finally { setBusy(false); }
  };
  const set = (key: keyof Form) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((value) => ({ ...value, [key]: event.target.value }));
  const save = async () => {
    setBusy(true); setNotice(null);
    try {
      await saveUserTemplate({ ...raw, ...form,
        tools: Array.isArray(raw.tools) ? raw.tools : [],
        skills: Array.isArray(raw.skills) ? raw.skills : [],
      });
      setNotice("Template saved."); setSelected(form.id); refresh();
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : "Couldn’t save template."); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!selected) return;
    setBusy(true); setNotice(null);
    try { await deleteUserTemplate(selected); setSelected(null); setForm(EMPTY); setRaw({}); refresh(); }
    catch (cause) { setNotice(cause instanceof Error ? cause.message : "Couldn’t delete template."); }
    finally { setBusy(false); }
  };
  const fork = async () => {
    if (!selected) return;
    setBusy(true); setNotice(null);
    const newId = `${selected}-fork`;
    try {
      const id = await forkTemplate(selected, newId);
      setUserIds((prev) => new Set(prev).add(id));
      setSelected(id); refresh();
      setNotice("Forked a private copy you can edit.");
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : "Couldn’t fork this template."); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    if (!selected) return;
    setBusy(true); setNotice(null);
    try {
      await resetTemplate(selected);
      await choose({ id: selected, name: form.name, description: form.description, model: form.model } as Persona);
      setNotice("Reset to the original template.");
    } catch (cause) { setNotice(cause instanceof Error ? cause.message : "Couldn’t reset — this template may not be a fork."); }
    finally { setBusy(false); }
  };

  const caps = capabilities.status === "ready" ? capabilities.caps : null;
  const canCreate = caps?.agent_templates.create === true;
  const canDelete = caps?.agent_templates.delete === true;
  const canFork = caps?.agent_templates.fork === true;
  const canReset = caps?.agent_templates.reset === true;
  const isUserTemplate = selected !== null && userIds.has(selected);
  // The New button sets `selected` to null; a user template always keeps its editor.
  const showEditor = selected === null ? canCreate : isUserTemplate;

  return (
    <section aria-labelledby="templates-title" className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
      <div className="min-w-0"><div className="mb-3 flex items-center justify-between">
        <div><h2 id="templates-title" className="text-lg font-semibold">Agent Templates</h2>
          <p className="text-xs text-muted-foreground">Personas agents use for chat and crews.</p></div>
        {canCreate && <button type="button" onClick={() => { setSelected(null); setForm(EMPTY); setRaw({}); setNotice(null); }}
          aria-label="New agent template" className="rounded-md border border-border/60 p-2 hover:bg-accent/40"><Plus className="h-4 w-4" /></button>}
      </div>
      {loading ? <p className="text-sm text-muted-foreground">Loading templates…</p>
        : error ? <p role="alert" className="text-sm text-destructive">{error}</p>
        : <div className="flex flex-col gap-1">{personas.map((persona) => <button key={persona.id}
          type="button" onClick={() => void choose(persona)} aria-current={selected === persona.id}
          className={`rounded-md px-3 py-2 text-left ${selected === persona.id ? "bg-violet-500/15" : "hover:bg-accent/30"}`}>
          <span className="block truncate text-sm font-medium">{persona.name}</span>
          <span className="block truncate text-[10px] text-muted-foreground">{userIds.has(persona.id) ? "User template" : "Built-in"}</span>
        </button>)}</div>}
      {caps && !caps.config.read && <p className="mt-3 text-[11px] text-muted-foreground">{authoringGateNotice(caps, "config", "read")}</p>}
      </div>
      <div className="rounded-xl border border-border/60 bg-card/20 p-5">
        {busy && <Loader2 className="mb-2 h-4 w-4 animate-spin text-muted-foreground" />}
        {capabilities.status === "failed" ? <div><h3 className="font-semibold">Agent authoring unavailable</h3>
          <p className="mt-2 text-sm text-muted-foreground">{capabilities.message}</p></div>
          : capabilities.status === "checking" ? <p className="text-sm text-muted-foreground">Checking authoring access…</p>
          : selected === null && !canCreate ? <div><h3 className="font-semibold">New agent template</h3>
          <p className="mt-2 text-[11px] text-muted-foreground">{authoringGateNotice(capabilities.caps, "agent_templates", "create")}</p></div>
          : !showEditor ? <div><h3 className="font-semibold">{form.name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{form.description || "Built-in template"}</p>
          <p className="mt-4 text-xs text-muted-foreground">Built-in templates are read-only.</p>
          {canFork && selected && <button type="button" onClick={() => void fork()} disabled={busy}
            aria-label="Fork this template" className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-2 text-xs text-muted-foreground hover:bg-accent/30 hover:text-foreground">
            <GitFork className="h-3.5 w-3.5" /> Fork to edit a copy</button>}
          {caps && !canFork && selected && <p className="mt-3 text-[11px] text-muted-foreground">{authoringGateNotice(caps, "agent_templates", "fork")}</p>}</div>
          : <div className="grid gap-3">
            {caps && !canCreate && <p className="text-[11px] text-muted-foreground">{authoringGateNotice(caps, "agent_templates", "create")}</p>}
            <Field label="ID"><input value={form.id} onChange={set("id")} disabled={!canCreate || selected !== null} /></Field>
            <Field label="Name"><input value={form.name} onChange={set("name")} disabled={!canCreate} /></Field>
            <Field label="Description"><input value={form.description} onChange={set("description")} disabled={!canCreate} /></Field>
            <Field label="Model"><input value={form.model} onChange={set("model")} disabled={!canCreate} /></Field>
            <Field label="System prompt"><textarea value={form.system_prompt} onChange={set("system_prompt")} rows={6} disabled={!canCreate} /></Field>
            <div className="flex gap-2">{canCreate && <button type="button" onClick={() => void save()} disabled={busy || !form.id || !form.name || !form.system_prompt}
              className="inline-flex items-center gap-1.5 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40"><Save className="h-3.5 w-3.5" /> Save</button>}
              {selected && canReset && <button type="button" onClick={() => void reset()} disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-2 text-xs text-muted-foreground hover:bg-accent/30 hover:text-foreground"><RotateCcw className="h-3.5 w-3.5" /> Reset</button>}
              {selected && canDelete && <button type="button" onClick={() => void remove()} disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-2 text-xs text-destructive"><Trash2 className="h-3.5 w-3.5" /> Delete</button>}</div>
            {selected && caps && !canReset && <p className="text-[11px] text-muted-foreground">{authoringGateNotice(caps, "agent_templates", "reset")}</p>}
            {selected && caps && !canDelete && <p className="text-[11px] text-muted-foreground">{authoringGateNotice(caps, "agent_templates", "delete")}</p>}
          </div>}
        {notice && <p role="status" className="mt-3 text-xs text-muted-foreground">{notice}</p>}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactElement }) {
  return <label className="grid gap-1 text-xs text-muted-foreground">{label}
    <span className="[&>input]:w-full [&>input]:rounded-md [&>input]:border [&>input]:border-border/60 [&>input]:bg-background/50 [&>input]:px-3 [&>input]:py-2 [&>textarea]:w-full [&>textarea]:rounded-md [&>textarea]:border [&>textarea]:border-border/60 [&>textarea]:bg-background/50 [&>textarea]:px-3 [&>textarea]:py-2 [&>input]:text-foreground [&>textarea]:text-foreground">{children}</span>
  </label>;
}
