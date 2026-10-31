"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, Laptop, Loader2, LockKeyhole, MousePointer2, Plug } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import { addExternalServer } from "@/components/connections/external-servers-api";

interface CuStatus {
  platformSupported: boolean; mounted: boolean; serverName: string | null; toolNames: string[];
  presetName: string; presetCommand: string; presetArgs: string[]; presetCommandFound: boolean;
  presetCommandPath: string | null; accessibilityHint: string;
}

function statusFrom(raw: unknown): CuStatus {
  const v = unwrapToolData(raw) as Record<string, unknown>;
  if (typeof v.mounted !== "boolean") throw new Error("Computer Use status unavailable.");
  const strs = (x: unknown) => (Array.isArray(x) ? x.filter((s): s is string => typeof s === "string") : []);
  return {
    platformSupported: v.platform_supported === true, mounted: v.mounted,
    serverName: typeof v.server_name === "string" ? v.server_name : null, toolNames: strs(v.tool_names),
    presetName: String(v.preset_name ?? "computer"), presetCommand: String(v.preset_command ?? "kirocrew"),
    presetArgs: strs(v.preset_args), presetCommandFound: v.preset_command_found === true,
    presetCommandPath: typeof v.preset_command_path === "string" ? v.preset_command_path : null,
    accessibilityHint: typeof v.accessibility_hint === "string" ? v.accessibility_hint : "",
  };
}

const SAFEGUARDS = [
  { icon: LockKeyhole, title: "Protected fields", detail: "Password fields are never readable, writable, or captured — enforced by the desktop server itself." },
  { icon: MousePointer2, title: "Pointer-safe by default", detail: "Controls are pressed through accessibility without moving your pointer; pointer-moving clicks must be asked for by name." },
  { icon: Laptop, title: "Scope = your approval list", detail: "Any computer_* tool can be named on the one approval list in Security. Nothing else gates it." },
] as const;

/**
 * Settings → Computer Use. Desktop automation is an external MCP server mounted
 * through Connections (the KiroCrew `mcp-computer` server is the bundled preset);
 * this page shows whether one is mounted and registers the preset in one click.
 */
export default function ComputerUseSettingsPanel() {
  const [status, setStatus] = useState<CuStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try { setStatus(statusFrom(await callTool("connections_computer_use_status"))); setError(null); }
    catch { setError("Computer Use status unavailable."); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const register = async () => {
    if (!status) return;
    setBusy(true); setNote(null);
    try {
      const server = await addExternalServer(status.presetName, {
        transport: "stdio", command: status.presetCommand, args: status.presetArgs, enabled: true,
      });
      setNote(server.mounted ? `Mounted ${server.toolsCount} desktop tools as mcp-${server.name}.`
        : `Registered ${server.name}, but it did not mount — is the KiroCrew app running with Computer Use on?`);
      await refresh();
    } catch (cause) { setNote(cause instanceof Error ? cause.message : "Registration failed."); }
    finally { setBusy(false); }
  };

  return <section aria-labelledby="computer-use-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="computer-use-settings-title" className="text-sm font-semibold">Computer Use</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Lets agents read and drive your desktop apps (macOS) through a desktop-automation MCP server.</p>
    {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
    {status && <div className="mt-4 rounded-md border border-border/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-[10px] font-medium uppercase tracking-wider text-violet-300">Desktop server</p>
          <p className="mt-0.5 text-sm font-medium">{status.mounted ? `Mounted — ${status.serverName} (${status.toolNames.length} tools)` : "Not mounted"}</p>
          {!status.platformSupported && <p className="mt-1 text-xs text-amber-400">Desktop automation is macOS-only; this host is not macOS.</p>}
          {status.platformSupported && !status.mounted && <p className="mt-1 text-xs text-amber-400">Agents have no desktop tools until a computer server is mounted.</p>}</div>
        {!status.mounted && <button type="button" onClick={() => void register()} disabled={busy || !status.presetCommandFound}
          className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-50">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5" />} Register the KiroCrew computer server</button>}
      </div>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <Row label="Preset command" value={`${status.presetCommand} ${status.presetArgs.join(" ")}`} ok />
        <Row label="Command on PATH" value={status.presetCommandFound ? status.presetCommandPath ?? "found" : "not found — install KiroCrew"} ok={status.presetCommandFound} />
      </dl>
      {note && <p role="status" className="mt-3 text-xs text-foreground/90">{note}</p>}
      <p className="mt-3 text-[11px] text-muted-foreground">{status.accessibilityHint}</p>
      {status.mounted && <a href="/capabilities?tab=connections" className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-violet-300 hover:text-violet-200">Manage in Connections<ArrowUpRight className="h-3.5 w-3.5" /></a>}
    </div>}
    <div className="mt-4 grid gap-3 sm:grid-cols-3">{SAFEGUARDS.map((item) => <article key={item.title} className="rounded-md border border-border/40 p-4">
      <item.icon className="h-5 w-5 text-violet-400" /><h3 className="mt-3 text-sm font-medium">{item.title}</h3>
      <p className="mt-1 text-xs text-muted-foreground">{item.detail}</p>
    </article>)}</div>
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">
      Not applicable here: a separate allowed/denied-app list. The one approval list is the only gate; secure-field refusal stays, enforced by the server.
    </p>
  </section>;
}

function Row({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return <div className="rounded-md border border-border/30 px-3 py-2">
    <dt className="text-[10px] text-muted-foreground">{label}</dt>
    <dd className={`m-0 truncate font-mono text-[11px] ${ok ? "text-foreground/90" : "text-amber-400"}`} title={value}>{value}</dd>
  </div>;
}
