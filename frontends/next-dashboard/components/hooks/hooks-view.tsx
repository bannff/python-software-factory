"use client";
import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw, Trash2, Webhook } from "lucide-react";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import { AGENT_LIFECYCLE_EVENTS, deleteHook, hookAuthoringAvailable, listHooks,
  listInvocableTools, listRecentFirings, saveHook,
  type Hook, type HookFiring } from "./hooks-api";

const EMPTY: Hook = { id: "", eventType: AGENT_LIFECYCLE_EVENTS[0].value, tool: "", description: "", enabled: true };

export default function HooksView() {
  const { ready, status } = useMcpConnection();
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [tools, setTools] = useState<string[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [creating, setCreating] = useState(false);
  const [canWrite, setCanWrite] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [firings, setFirings] = useState<Record<string, HookFiring[]>>({});

  const refresh = useCallback(async () => {
    if (!ready) return;
    setLoading(true); setError(null);
    try {
      const [rows, writable, invocable] = await Promise.all([listHooks(), hookAuthoringAvailable(), listInvocableTools()]);
      setHooks(rows); setCanWrite(writable); setTools(invocable);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Hooks unavailable."); }
    finally { setLoading(false); }
  }, [ready]);
  useEffect(() => { void refresh(); }, [refresh]);

  const loadFirings = async (hook: Hook) => {
    try {
      const rows = await listRecentFirings(hook.eventType);
      setFirings((value) => ({ ...value, [hook.id]: rows }));
    } catch { /* recent firings are a nice-to-have; a failed lookup should not block the row */ }
  };
  useEffect(() => { hooks.forEach((hook) => { void loadFirings(hook); }); }, [hooks]);

  const toggle = async (hook: Hook) => {
    setBusy(hook.id); setError(null);
    try { await saveHook({ ...hook, enabled: !hook.enabled }); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't update hook."); }
    finally { setBusy(null); }
  };
  const remove = async (hook: Hook) => {
    setBusy(hook.id); setError(null);
    try { await deleteHook(hook.id); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't delete hook."); }
    finally { setBusy(null); }
  };
  const create = async () => {
    setBusy(form.id); setError(null);
    try { await saveHook(form); setCreating(false); setForm(EMPTY); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn't create hook."); }
    finally { setBusy(null); }
  };

  return <section aria-labelledby="hooks-title">
    <div className="mb-4 flex items-start justify-between">
      <div><h2 id="hooks-title" className="text-lg font-semibold">Hooks</h2>
        <p className="text-xs text-muted-foreground">Run a tool automatically when your agent hits an event.</p></div>
      <div className="flex gap-1">{canWrite && <button type="button" aria-label="New hook" onClick={() => { setCreating(true); setForm(EMPTY); }}
        className="rounded-md border border-border/60 p-2 hover:bg-accent/40"><Plus className="h-4 w-4" /></button>}
        <button type="button" aria-label="Refresh hooks" onClick={() => void refresh()} disabled={!ready || loading}
          className="rounded-md border border-border/60 p-2 disabled:opacity-40"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button></div>
    </div>
    {error && <p role="alert" className="mb-3 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
    {!ready ? <p className="text-sm text-muted-foreground">MCP is {status}.</p>
      : creating ? <div className="max-w-2xl rounded-xl border border-border/60 bg-card/20 p-5">
        <h3 className="mb-3 font-semibold">New hook</h3>
        <div className="grid gap-3">
          <label className="grid gap-1 text-xs text-muted-foreground">Name
            <input value={form.id} onChange={(event) => setForm((value) => ({ ...value, id: event.target.value }))}
              className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-foreground" /></label>
          <label className="grid gap-1 text-xs text-muted-foreground">When
            <select value={form.eventType} onChange={(event) => setForm((value) => ({ ...value, eventType: event.target.value }))}
              className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-foreground">
              {AGENT_LIFECYCLE_EVENTS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select></label>
          <label className="grid gap-1 text-xs text-muted-foreground">Run this tool
            <input list="hooks-tool-options" value={form.tool} onChange={(event) => setForm((value) => ({ ...value, tool: event.target.value }))}
              placeholder="Start typing a tool name…" className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-foreground" />
            <datalist id="hooks-tool-options">{tools.map((tool) => <option key={tool} value={tool} />)}</datalist></label>
          <label className="grid gap-1 text-xs text-muted-foreground">Description (optional)
            <input value={form.description} onChange={(event) => setForm((value) => ({ ...value, description: event.target.value }))}
              className="rounded-md border border-border/60 bg-background/50 px-3 py-2 text-foreground" /></label>
        </div>
        <div className="mt-4 flex gap-2">
          <button type="button" onClick={() => void create()} disabled={Boolean(busy) || !form.id || !form.tool}
            className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Create hook</button>
          <button type="button" onClick={() => setCreating(false)} className="rounded-md border border-border/60 px-3 py-2 text-xs">Cancel</button>
        </div>
      </div>
      : loading && hooks.length === 0 ? <p className="text-sm text-muted-foreground">Loading hooks…</p>
      : hooks.length === 0 ? <div className="rounded-xl border border-dashed border-border/60 p-8 text-center text-muted-foreground">
        <Webhook className="mx-auto mb-3 h-8 w-8 text-violet-400" /><p>No hooks configured.</p></div>
      : <div className="grid gap-3 md:grid-cols-2">{hooks.map((hook) => {
        const event = AGENT_LIFECYCLE_EVENTS.find((option) => option.value === hook.eventType);
        const recent = firings[hook.id] ?? [];
        return <article key={hook.id} className="rounded-xl border border-border/60 bg-card/20 p-4">
          <div className="flex items-start justify-between gap-3">
            <div><h3 className="font-medium">{hook.id}</h3>
              <p className="text-xs text-muted-foreground">When {event?.label ?? hook.eventType}</p></div>
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => void toggle(hook)} disabled={!canWrite || busy === hook.id} aria-pressed={hook.enabled}
                className={`rounded-full px-2 py-1 text-[10px] ${hook.enabled ? "bg-emerald-500/10 text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                {hook.enabled ? "Enabled" : "Disabled"}</button>
              {canWrite && <button type="button" aria-label={`Delete hook ${hook.id}`} onClick={() => void remove(hook)} disabled={busy === hook.id}
                className="rounded-md p-1 text-destructive disabled:opacity-40"><Trash2 className="h-3.5 w-3.5" /></button>}
            </div>
          </div>
          <p className="mt-3 font-mono text-xs">Runs: {hook.tool}</p>
          {hook.description && <p className="mt-2 text-xs text-muted-foreground">{hook.description}</p>}
          <p className="mt-3 text-[11px] text-muted-foreground">
            {recent.length === 0 ? "No recent firings." : `Last fired ${new Date(recent[0].timestamp).toLocaleString()} (${recent.length} recent)`}
          </p>
        </article>;
      })}</div>}
    {!canWrite && ready && !loading && <p className="mt-3 text-[11px] text-muted-foreground">Hook changes are disabled by the Events authoring gate.</p>}
  </section>;
}
