"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { AddServerDialog } from "./add-server-dialog";
import { reloadCapabilities } from "./connections-api";
import {
  addExternalServer, importExternalServers, listExternalServers,
  removeExternalServer, specFrom, updateExternalServer, type ExternalServer,
} from "./external-servers-api";

interface ExternalServersPanelProps {
  ready: boolean;
  /** Called after any change so the parent can refresh the gateway brick list. */
  onChanged: () => void;
}

export function ExternalServersPanel({ ready, onChanged }: ExternalServersPanelProps) {
  const [servers, setServers] = useState<ExternalServer[]>([]);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!ready) return;
    try { setServers(await listExternalServers()); setError(null); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Servers unavailable."); }
  }, [ready]);
  useEffect(() => { void refresh(); }, [refresh]);

  const run = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key); setError(null);
    try { await action(); await refresh(); onChanged(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Operation failed."); }
    finally { setBusy(null); }
  };

  return (
    <section aria-labelledby="external-servers-title" className="mb-4 rounded-xl border border-border/60 bg-card/20 p-4">
      <div className="flex items-start justify-between gap-2">
        <div><h3 id="external-servers-title" className="text-sm font-semibold">External MCP servers</h3>
          <p className="text-xs text-muted-foreground">Your own servers, mounted as powers for every agent.</p></div>
        <div className="flex gap-1">
          <button type="button" onClick={() => void run("reload", reloadCapabilities)} disabled={!ready || busy !== null}
            aria-label="Reload capabilities" title="Re-discover bricks, personas, skills, and external servers without a restart"
            className="rounded-md border border-border/60 p-2 hover:bg-accent/40 disabled:opacity-40">
            <RefreshCw className={`h-4 w-4 ${busy === "reload" ? "animate-spin" : ""}`} /></button>
          <button type="button" onClick={() => setAdding(true)} disabled={!ready}
            className="inline-flex items-center gap-1 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
            <Plus className="h-3.5 w-3.5" /> Add server</button>
        </div>
      </div>
      {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
      {servers.length === 0 ? <p className="mt-3 text-xs text-muted-foreground">No external servers yet. Add one, or paste an mcpServers JSON block.</p>
        : <ul className="mt-3 space-y-1">{servers.map((server) => <li key={server.name}
          className="flex items-center gap-3 rounded-md border border-border/40 px-3 py-2 text-xs">
          <span className={`h-2 w-2 shrink-0 rounded-full ${server.mounted ? "bg-emerald-400" : server.enabled ? "bg-amber-400" : "bg-muted-foreground/40"}`}
            title={server.mounted ? "Mounted" : server.enabled ? "Enabled, not reachable" : "Disabled"} />
          <span className="min-w-0 flex-1"><span className="block truncate font-medium">{server.name}</span>
            <span className="block truncate font-mono text-[10px] text-muted-foreground">
              {server.transport === "stdio" ? [server.command, ...server.args].join(" ") : server.url}</span>
            {server.unresolvedEnv.length > 0 && <span role="alert" className="block text-[10px] text-amber-400">
              Not set in the server environment: {server.unresolvedEnv.join(", ")}</span>}</span>
          <span className="text-[10px] text-muted-foreground">{server.mounted ? `${server.toolsCount} tools` : server.enabled ? "unreachable" : "off"}</span>
          <label className="flex items-center gap-1 text-[10px]"><input type="checkbox" checked={server.enabled}
            aria-label={`Enable ${server.name}`} disabled={busy !== null}
            onChange={(event) => void run(server.name, () => updateExternalServer(
              server.name, specFrom(server, event.target.checked), server.revision))} /> on</label>
          <button type="button" aria-label={`Remove ${server.name}`} disabled={busy !== null}
            onClick={() => void run(server.name, () => removeExternalServer(server.name, server.revision))}
            className="rounded p-1 text-muted-foreground hover:text-destructive disabled:opacity-40">
            {busy === server.name ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}</button>
        </li>)}</ul>}
      {adding && <AddServerDialog onClose={() => setAdding(false)}
        onAdd={async (name, spec) => { await addExternalServer(name, spec); await refresh(); onChanged(); }}
        onImport={async (document) => { await importExternalServers(document); await refresh(); onChanged(); }} />}
    </section>
  );
}
