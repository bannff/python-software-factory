"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, PlugZap, RefreshCw, Search, Server } from "lucide-react";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import {
  enableConnectionBrick, listConnectionBricks,
  type ConnectionBrick, type ConnectionTool,
} from "./connections-api";
import { ExternalServersPanel } from "./external-servers-panel";

export default function ConnectionsView() {
  const { ready, status } = useMcpConnection();
  const [bricks, setBricks] = useState<ConnectionBrick[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [tools, setTools] = useState<ConnectionTool[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [enabling, setEnabling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!ready) return;
    setLoading(true); setError(null);
    try { setBricks(await listConnectionBricks()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Connections unavailable."); }
    finally { setLoading(false); }
  }, [ready]);
  useEffect(() => { void refresh(); }, [refresh]);

  const rows = useMemo(() => bricks.filter((brick) =>
    `${brick.name} ${brick.namespace}`.toLowerCase().includes(query.toLowerCase()),
  ).sort((a, b) => Number(b.loaded) - Number(a.loaded) || a.name.localeCompare(b.name)), [bricks, query]);
  const active = bricks.find((brick) => brick.name === selected) ?? null;
  const loaded = bricks.filter((brick) => brick.loaded).length;
  const knownTools = bricks.reduce((sum, brick) => sum + Math.max(0, brick.toolsCount), 0);

  const inspect = async (brick: ConnectionBrick) => {
    setSelected(brick.name); setTools([]); setError(null);
    if (!brick.loaded) return;
    setEnabling(brick.name);
    try { setTools(await enableConnectionBrick(brick.name)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Tool inventory unavailable."); }
    finally { setEnabling(null); }
  };
  const enable = async (brick: ConnectionBrick) => {
    setEnabling(brick.name); setError(null);
    try {
      const nextTools = await enableConnectionBrick(brick.name);
      setSelected(brick.name); setTools(nextTools); await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn’t enable connection."); }
    finally { setEnabling(null); }
  };

  return (
    <section aria-labelledby="connections-title" className="grid gap-4 lg:grid-cols-[21rem_minmax(0,1fr)]">
      <div className="lg:col-span-2"><ExternalServersPanel ready={ready} onChanged={() => void refresh()} /></div>
      <div className="min-w-0"><div className="mb-3 flex items-start justify-between gap-2">
        <div><h2 id="connections-title" className="text-lg font-semibold">Connections</h2>
          <p className="text-xs text-muted-foreground">MCP powers available to this Companion-X deployment.</p></div>
        <button type="button" onClick={() => void refresh()} disabled={!ready || loading}
          aria-label="Refresh connections" className="rounded-md border border-border/60 p-2 hover:bg-accent/40 disabled:opacity-40">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></button>
      </div>
      <div className="mb-3 grid grid-cols-3 gap-2 text-center text-xs">
        <Stat value={bricks.length} label="Registered" /><Stat value={loaded} label="Enabled" />
        <Stat value={knownTools} label="Known tools" />
      </div>
      <label className="mb-2 flex items-center gap-2 rounded-md border border-border/60 px-2 text-muted-foreground">
        <Search className="h-3.5 w-3.5" /><span className="sr-only">Search connections</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search powers"
          className="w-full bg-transparent py-2 text-xs text-foreground outline-none" /></label>
      {!ready ? <p className="text-sm text-muted-foreground">MCP is {status}.</p>
        : loading && bricks.length === 0 ? <p className="text-sm text-muted-foreground">Loading connections…</p>
        : rows.length === 0 ? <p className="text-sm text-muted-foreground">No matching connections.</p>
        : <div className="space-y-1 pr-1">{rows.map((brick) => <button
          key={brick.name} type="button" onClick={() => void inspect(brick)} aria-current={selected === brick.name}
          className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left ${selected === brick.name ? "bg-violet-500/15" : "hover:bg-accent/30"}`}>
          <Server className={`h-4 w-4 shrink-0 ${brick.loaded ? "text-emerald-400" : "text-muted-foreground"}`} />
          <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{brick.name}</span>
            <span className="block truncate text-[10px] text-muted-foreground">{brick.namespace}</span></span>
          <span className="text-[10px] text-muted-foreground">{brick.loaded ? `${brick.toolsCount} tools` : "Available"}</span>
        </button>)}</div>}
      </div>
      <div className="min-h-72 rounded-xl border border-border/60 bg-card/20 p-5">
        {error && <div role="alert" className="mb-3 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">{error}</div>}
        {!active ? <div className="flex min-h-56 flex-col items-center justify-center text-center text-muted-foreground">
          <PlugZap className="mb-3 h-8 w-8 text-violet-400" /><p className="text-sm">Select an MCP power to inspect or enable it.</p></div>
          : <><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{active.name}</h3>
            <p className="mt-1 font-mono text-xs text-muted-foreground">{active.namespace}</p></div>
            <span className={`rounded-full px-2 py-1 text-[10px] ${active.loaded ? "bg-emerald-500/10 text-emerald-300" : "bg-muted text-muted-foreground"}`}>
              {active.loaded ? "Enabled" : "Not loaded"}</span></div>
            {active.error && <p className="mt-3 text-xs text-destructive">{active.error}</p>}
            {!active.loaded ? <div className="mt-6"><p className="text-sm text-muted-foreground">This power is registered but has not loaded tools into the MCP runtime.</p>
              <button type="button" onClick={() => void enable(active)} disabled={enabling === active.name}
                className="mt-4 inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-50">
                {enabling === active.name && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Enable power</button></div>
              : <div className="mt-5"><h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tools ({tools.length || active.toolsCount})</h4>
                {enabling === active.name ? <Loader2 className="mt-3 h-4 w-4 animate-spin text-muted-foreground" />
                  : tools.length === 0 ? <p className="mt-2 text-xs text-muted-foreground">Select again to refresh admitted tools.</p>
                  : <div className="mt-2 max-h-96 space-y-2 overflow-y-auto">{tools.map((tool) => <div key={tool.name} className="rounded-md border border-border/50 p-2">
                    <div className="flex gap-2"><code className="text-xs text-violet-300">{tool.name}</code>{tool.category && <span className="text-[10px] text-muted-foreground">{tool.category}</span>}</div>
                    {tool.description && <p className="mt-1 text-[11px] text-muted-foreground">{tool.description}</p>}</div>)}</div>}</div>}</>}
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return <div aria-label={`${label}: ${value}`} className="rounded-md border border-border/50 bg-card/20 px-2 py-2"><strong className="block text-sm text-foreground">{value}</strong>{label}</div>;
}
