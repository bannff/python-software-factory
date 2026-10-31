"use client";

import { useCallback, useEffect, useState } from "react";
import { Compass, Loader2, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import { authoringGateNotice, getAuthoringCapabilities,
  type AuthoringCapabilities } from "@/lib/authoring-capabilities";
import { deleteSteering, listSteering, readSteering, saveSteering,
  type SteeringDocument } from "./steering-api";

export default function SteeringView() {
  const { ready, status } = useMcpConnection();
  const [documents, setDocuments] = useState<SteeringDocument[]>([]);
  const [active, setActive] = useState<Required<SteeringDocument> | null>(null);
  const [id, setId] = useState("");
  const [content, setContent] = useState("");
  const [creating, setCreating] = useState(false);
  const [caps, setCaps] = useState<AuthoringCapabilities | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!ready) return;
    setLoading(true); setError(null);
    try {
      const [rows, capabilities] = await Promise.all([listSteering(), getAuthoringCapabilities()]);
      setDocuments(rows); setCaps(capabilities);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Steering unavailable."); }
    finally { setLoading(false); }
  }, [ready]);
  useEffect(() => { void refresh(); }, [refresh]);

  const select = async (document: SteeringDocument) => {
    setCreating(false); setBusy(true); setError(null);
    try { const row = await readSteering(document.id); setActive(row); setId(row.id); setContent(row.content); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Document unavailable."); }
    finally { setBusy(false); }
  };
  const startCreate = () => { setCreating(true); setActive(null); setId(""); setContent(""); setError(null); };
  const save = async () => {
    setBusy(true); setError(null);
    try {
      const row = await saveSteering({ id, content, ...(active ? { expectedSha256: active.sha256 } : {}) });
      setActive(row); setCreating(false); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn’t save steering."); }
    finally { setBusy(false); }
  };
  const remove = async () => {
    if (!active) return;
    setBusy(true); setError(null);
    try { await deleteSteering(active.id, active.sha256); setActive(null); setCreating(false); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn’t delete steering."); }
    finally { setBusy(false); }
  };

  // Creating a document rides `steering.create`; saving an existing one `steering.update`.
  const saving = creating ? caps?.steering.create === true : caps?.steering.update === true;

  return <section aria-labelledby="steering-title" className="grid gap-4 lg:grid-cols-[19rem_minmax(0,1fr)]">
    <div><div className="mb-3 flex items-start justify-between"><div><h2 id="steering-title" className="text-lg font-semibold">Steering</h2>
      <p className="text-xs text-muted-foreground">Instructions injected into every Agent prompt.</p></div>
      <div className="flex gap-1">{caps?.steering.create && <button type="button" aria-label="New steering document" onClick={startCreate}
        className="rounded-md border border-border/60 p-2 hover:bg-accent/40"><Plus className="h-4 w-4" /></button>}
        <button type="button" aria-label="Refresh steering" onClick={() => void refresh()} disabled={!ready || loading}
          className="rounded-md border border-border/60 p-2 disabled:opacity-40"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button></div></div>
      {!ready ? <p className="text-sm text-muted-foreground">MCP is {status}.</p>
        : loading && documents.length === 0 ? <p className="text-sm text-muted-foreground">Loading steering…</p>
        : documents.length === 0 ? <p className="text-sm text-muted-foreground">No steering documents yet.</p>
        : <div className="space-y-1">{documents.map((document) => <button key={document.id} type="button"
          onClick={() => void select(document)} aria-current={active?.id === document.id}
          className={`w-full rounded-md px-3 py-2 text-left ${active?.id === document.id ? "bg-violet-500/15" : "hover:bg-accent/30"}`}>
          <span className="block truncate text-sm font-medium">{document.title}</span><code className="text-[10px] text-muted-foreground">{document.id}</code></button>)}</div>}
      {caps && !caps.steering.create && ready && !loading && <p className="mt-3 text-[11px] text-muted-foreground">{authoringGateNotice(caps, "steering", "create")}</p>}
    </div>
    <div className="min-h-72 rounded-xl border border-border/60 bg-card/20 p-5">
      {error && <p role="alert" className="mb-3 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
      {busy && <Loader2 className="mb-3 h-4 w-4 animate-spin" />}
      {creating || active ? <div className="grid gap-3"><h3 className="font-semibold">{creating ? "New steering document" : active?.title}</h3>
        <label className="grid gap-1 text-xs text-muted-foreground">ID<input value={id} onChange={(event) => setId(event.target.value)} disabled={!creating}
          className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-foreground" /></label>
        <label className="grid gap-1 text-xs text-muted-foreground">Markdown<textarea value={content} onChange={(event) => setContent(event.target.value)}
          readOnly={!saving} rows={15} className="rounded-md border border-border/60 bg-background/50 px-3 py-2 font-mono text-xs text-foreground" /></label>
        {caps && !saving && <p className="text-[11px] text-muted-foreground">{authoringGateNotice(caps, "steering", creating ? "create" : "update")}</p>}
        {(saving || (!creating && active && caps?.steering.delete)) && <div className="flex gap-2">{saving && <button type="button" onClick={() => void save()} disabled={busy || !id || !content.trim()}
          className="inline-flex w-fit items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40"><Save className="h-3.5 w-3.5" /> Save</button>}
          {!creating && active && caps?.steering.delete && <button type="button" aria-label="Delete steering document" onClick={() => void remove()} disabled={busy}
            className="inline-flex w-fit items-center gap-2 rounded-md border border-destructive/40 px-3 py-2 text-xs text-destructive disabled:opacity-40">
            <Trash2 className="h-3.5 w-3.5" /> Delete</button>}</div>}
        {!creating && active && caps && !caps.steering.delete && <p className="text-[11px] text-muted-foreground">{authoringGateNotice(caps, "steering", "delete")}</p>}</div>
        : <div className="flex min-h-56 flex-col items-center justify-center text-center text-muted-foreground"><Compass className="mb-3 h-8 w-8 text-violet-400" />
          <p className="text-sm">Select a steering document to read or edit it.</p></div>}
    </div>
  </section>;
}
