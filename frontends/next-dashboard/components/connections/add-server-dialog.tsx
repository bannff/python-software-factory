"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import type { ExternalServerSpec } from "./external-servers-api";

interface AddServerDialogProps {
  onAdd: (name: string, spec: ExternalServerSpec) => Promise<void>;
  onImport: (document: string) => Promise<void>;
  onClose: () => void;
}

const PLACEHOLDER = `{
  "mcpServers": {
    "github": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": { "GITHUB_TOKEN": "GITHUB_TOKEN" } }
  }
}`;

function parseKeyValues(text: string): Record<string, string> {
  return Object.fromEntries(text.split(/\n|,/).map((line) => line.trim()).filter(Boolean)
    .map((line) => line.split("=").map((part) => part.trim()))
    .filter((pair): pair is [string, string] => pair.length === 2 && Boolean(pair[0]) && Boolean(pair[1])));
}

export function AddServerDialog({ onAdd, onImport, onClose }: AddServerDialogProps) {
  const [mode, setMode] = useState<"form" | "json">("form");
  const [name, setName] = useState("");
  const [transport, setTransport] = useState<"stdio" | "streamable_http">("stdio");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [url, setUrl] = useState("");
  const [secrets, setSecrets] = useState("");
  const [document, setDocument] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      if (mode === "json") await onImport(document);
      else {
        const spec: ExternalServerSpec = transport === "stdio"
          ? { transport, command: command.trim(), args: args.split(/\s+/).filter(Boolean), env: parseKeyValues(secrets), enabled: true }
          : { transport, url: url.trim(), headers: parseKeyValues(secrets), enabled: true };
        await onAdd(name.trim(), spec);
      }
      onClose();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Couldn’t add server."); }
    finally { setBusy(false); }
  };

  const field = "mt-1 w-full rounded-md border border-border/60 bg-background/50 px-3 py-2 text-xs";
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="add-server-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <form onSubmit={(event) => void submit(event)} className="w-full max-w-lg rounded-xl border border-border/60 bg-card p-5 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <h3 id="add-server-title" className="text-base font-semibold">Add MCP server</h3>
          <div role="tablist" aria-label="Add method" className="flex rounded-md border border-border/60 text-xs">
            {(["form", "json"] as const).map((item) => <button key={item} type="button" role="tab" aria-selected={mode === item}
              onClick={() => setMode(item)} className={`px-3 py-1 ${mode === item ? "bg-violet-500/15 text-violet-300" : "text-muted-foreground"}`}>
              {item === "form" ? "Form" : "JSON"}</button>)}
          </div>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">Secrets are referenced by environment variable name; values are read from the server process and never stored.</p>
        {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
        {mode === "json" ? <label className="mt-4 block text-xs"><span className="font-medium">mcpServers JSON</span>
          <textarea aria-label="mcpServers JSON" value={document} onChange={(event) => setDocument(event.target.value)}
            placeholder={PLACEHOLDER} rows={10} required className={`${field} font-mono`} /></label>
        : <div className="mt-4 grid gap-3 text-xs">
          <label><span className="font-medium">Name</span>
            <input aria-label="Server name" value={name} onChange={(event) => setName(event.target.value)} required pattern="[a-z0-9][a-z0-9_-]{0,63}" placeholder="github" className={field} /></label>
          <label><span className="font-medium">Transport</span>
            <select aria-label="Transport" value={transport} onChange={(event) => setTransport(event.target.value as "stdio" | "streamable_http")} className={field}>
              <option value="stdio">Command (stdio)</option><option value="streamable_http">URL (Streamable HTTP)</option></select></label>
          {transport === "stdio" ? <>
            <label><span className="font-medium">Command</span>
              <input aria-label="Command" value={command} onChange={(event) => setCommand(event.target.value)} required placeholder="npx" className={field} /></label>
            <label><span className="font-medium">Arguments</span>
              <input aria-label="Arguments" value={args} onChange={(event) => setArgs(event.target.value)} placeholder="-y @modelcontextprotocol/server-github" className={field} /></label>
          </> : <label><span className="font-medium">URL</span>
            <input aria-label="URL" type="url" value={url} onChange={(event) => setUrl(event.target.value)} required placeholder="https://example.com/mcp" className={field} /></label>}
          <label><span className="font-medium">{transport === "stdio" ? "Environment (NAME=SOURCE_ENV_NAME per line)" : "Headers (Header=SOURCE_ENV_NAME per line)"}</span>
            <textarea aria-label={transport === "stdio" ? "Environment" : "Headers"} value={secrets} onChange={(event) => setSecrets(event.target.value)}
              placeholder={transport === "stdio" ? "GITHUB_TOKEN=GITHUB_TOKEN" : "Authorization=MY_SERVICE_BEARER"} rows={3} className={`${field} font-mono`} /></label>
        </div>}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md border border-border/60 px-3 py-2 text-xs">Cancel</button>
          <button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />} {mode === "json" ? "Import" : "Add server"}</button>
        </div>
      </form>
    </div>
  );
}
