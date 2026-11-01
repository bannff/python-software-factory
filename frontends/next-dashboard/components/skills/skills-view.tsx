"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Loader2, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import { authoringGateNotice, getAuthoringCapabilities,
  type AuthoringCapabilities } from "@/lib/authoring-capabilities";
import { useSkillPolicy } from "./use-skill-policy";
import { addSkill, deleteSkill, listSkills, readSkill,
  type SkillDetail, type SkillSummary } from "./skills-api";

const EMPTY = { skillId: "", name: "", description: "", body: "" };

export default function SkillsView() {
  const { policy } = useSkillPolicy();
  const { ready, status } = useMcpConnection();
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [detail, setDetail] = useState<SkillDetail | null>(null);
  const [query, setQuery] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [creating, setCreating] = useState(false);
  const [caps, setCaps] = useState<AuthoringCapabilities | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!ready) return;
    setLoading(true); setError(null);
    try {
      const [rows, capabilities] = await Promise.all([listSkills(), getAuthoringCapabilities()]);
      setSkills(rows); setCaps(capabilities);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Skills unavailable."); }
    finally { setLoading(false); }
  }, [ready]);
  useEffect(() => { void refresh(); }, [refresh]);

  const rows = useMemo(() => skills.filter((skill) =>
    `${skill.name} ${skill.id} ${skill.description}`.toLowerCase().includes(query.toLowerCase()),
  ), [skills, query]);
  const select = async (skill: SkillSummary) => {
    setCreating(false); setBusy(true); setError(null);
    try { setDetail(await readSkill(skill.id)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Skill detail unavailable."); }
    finally { setBusy(false); }
  };
  const set = (key: keyof typeof EMPTY) => (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => setForm((value) => ({ ...value, [key]: event.target.value }));
  const create = async () => {
    setBusy(true); setError(null);
    try {
      const row = await addSkill(form);
      await refresh(); setDetail(await readSkill(row.id)); setCreating(false); setForm(EMPTY);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn’t add skill."); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!detail) return;
    setBusy(true); setError(null);
    try { await deleteSkill(detail.id); setDetail(null); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn’t remove skill."); }
    finally { setBusy(false); }
  };

  return (
    <section aria-labelledby="skills-title" className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
      <div className="min-w-0"><div className="mb-3 flex items-start justify-between gap-2">
        <div><h2 id="skills-title" className="text-lg font-semibold">Skills</h2>
          <p className="text-xs text-muted-foreground">Reusable instructions agents load on demand.</p></div>
        <div className="flex gap-1">{caps?.skills.add && <button type="button" aria-label="Add skill"
          onClick={() => { setCreating(true); setDetail(null); setForm(EMPTY); setError(null); }}
          className="rounded-md border border-border/60 p-2 hover:bg-accent/40"><Plus className="h-4 w-4" /></button>}
          <button type="button" aria-label="Refresh skills" onClick={() => void refresh()} disabled={!ready || loading}
            className="rounded-md border border-border/60 p-2 hover:bg-accent/40 disabled:opacity-40">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button></div>
      </div>
      <label className="mb-2 flex items-center gap-2 rounded-md border border-border/60 px-2 text-muted-foreground">
        <Search className="h-3.5 w-3.5" /><span className="sr-only">Search skills</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search skills"
          className="w-full bg-transparent py-2 text-xs text-foreground outline-none" /></label>
      {!ready ? <p className="text-sm text-muted-foreground">MCP is {status}.</p>
        : loading && skills.length === 0 ? <p className="text-sm text-muted-foreground">Loading skills…</p>
        : rows.length === 0 ? <p className="text-sm text-muted-foreground">No matching skills.</p>
        : <div className="max-h-[32rem] space-y-1 overflow-y-auto pr-1">{rows.map((skill) => <button
          key={skill.id} type="button" onClick={() => void select(skill)} aria-current={detail?.id === skill.id}
          className={`w-full rounded-md px-3 py-2 text-left ${detail?.id === skill.id ? "bg-violet-500/15" : "hover:bg-accent/30"}`}>
          <span className="flex items-center gap-2 truncate text-sm font-medium">{skill.name}
            {policy.disabledSkills.includes(skill.id) && <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground" title="Switched off in Settings → Skills">Off for you</span>}</span>
          <span className="block truncate font-mono text-[10px] text-muted-foreground">{skill.id}</span>
          {skill.description && <span className="mt-1 block line-clamp-2 text-[11px] text-muted-foreground">{skill.description}</span>}
        </button>)}</div>}
      {caps && !caps.skills.add && ready && !loading && <p className="mt-3 text-[11px] text-muted-foreground">{authoringGateNotice(caps, "skills", "add")}</p>}
      </div>
      <div className="min-h-72 rounded-xl border border-border/60 bg-card/20 p-5">
        {error && <div role="alert" className="mb-3 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{error}</div>}
        {busy && <Loader2 className="mb-3 h-4 w-4 animate-spin text-muted-foreground" />}
        {creating ? <div className="grid gap-3"><h3 className="font-semibold">Add skill</h3>
          <Field label="ID"><input value={form.skillId} onChange={set("skillId")} placeholder="review-evidence" /></Field>
          <Field label="Name"><input value={form.name} onChange={set("name")} /></Field>
          <Field label="Description"><input value={form.description} onChange={set("description")} /></Field>
          <Field label="Instructions"><textarea value={form.body} onChange={set("body")} rows={10} /></Field>
          <div className="flex gap-2"><button type="button" onClick={() => void create()}
            disabled={busy || !form.skillId || !form.name.trim() || !form.body.trim()}
            className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Add skill</button>
            <button type="button" onClick={() => setCreating(false)} className="rounded-md border border-border/60 px-3 py-2 text-xs">Cancel</button></div></div>
          : detail ? <article><div className="flex items-start justify-between gap-2">
            <div><p className="text-xs font-medium uppercase tracking-wide text-violet-400">Skill</p>
            <h3 className="mt-1 text-lg font-semibold">{detail.name}</h3><code className="text-xs text-muted-foreground">{detail.id}</code></div>
            {caps?.skills.delete && <ConfirmDelete label="Delete skill" onConfirm={() => void remove()} disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-2 text-xs text-destructive disabled:opacity-40"><Trash2 className="h-3.5 w-3.5" /> Delete</ConfirmDelete>}</div>
            {caps && !caps.skills.delete && <p className="mt-2 text-[11px] text-muted-foreground">{authoringGateNotice(caps, "skills", "delete")}</p>}
            {detail.description && <p className="mt-3 text-sm text-muted-foreground">{detail.description}</p>}
            <pre className="mt-5 max-h-[26rem] overflow-auto whitespace-pre-wrap rounded-md border border-border/50 bg-background/50 p-4 font-sans text-xs leading-relaxed">{detail.body}</pre></article>
          : <div className="flex min-h-56 flex-col items-center justify-center text-center text-muted-foreground">
            <BookOpen className="mb-3 h-8 w-8 text-violet-400" /><p className="text-sm">Select a skill to read its instructions.</p></div>}
      </div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactElement }) {
  return <label className="grid gap-1 text-xs text-muted-foreground">{label}<span className="[&>*]:w-full [&>*]:rounded-md [&>*]:border [&>*]:border-border/60 [&>*]:bg-background/50 [&>*]:px-3 [&>*]:py-2 [&>*]:text-foreground">{children}</span></label>;
}
