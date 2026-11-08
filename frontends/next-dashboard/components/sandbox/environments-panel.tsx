"use client";

import { useCallback, useEffect, useState } from "react";
import { Box, Plus, Power } from "lucide-react";
import { ConfirmDelete } from "@/components/ui/confirm-delete";
import { EmptyState } from "@/components/ui/empty-state";
import { useMounted } from "@/lib/hooks/use-mounted";
import { cn } from "@/lib/utils";
import { useMutationRefresh } from "@/components/canvas/refresh-context";
import { listDevicePresets, listEnvironments, listProfiles, provision, sandboxFailure, terminate, type Environment } from "./sandbox-api";

const FIELD = "rounded-md border bg-background/50 px-3 py-2 text-sm";
const STATUS: Record<string, string> = { running: "bg-emerald-500/10 text-emerald-400", provisioning: "bg-amber-500/10 text-amber-400" };

/** Start and stop sandbox environments, driven by the sandbox_* tools. */
export function EnvironmentsPanel() {
  const [envs, setEnvs] = useState<Environment[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [choice, setChoice] = useState<{ profiles: string[]; presets: string[]; profile: string; preset: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useMounted();
  const { version, notify } = useMutationRefresh();

  const refresh = useCallback(async () => {
    try { const next = await listEnvironments(); if (mounted.current) setEnvs(next); }
    catch (cause) { if (mounted.current) setNotice(sandboxFailure("Environments are unavailable.", cause)); }
    finally { if (mounted.current) setLoaded(true); }
  }, [mounted]);
  useEffect(() => { void refresh(); }, [refresh, version]);

  const open = async () => {
    setNotice(null);
    try {
      const [profiles, presets] = await Promise.all([listProfiles(), listDevicePresets()]);
      setChoice({ profiles, presets, profile: "", preset: "" });
    } catch (cause) { setNotice(sandboxFailure("Profiles are unavailable.", cause)); }
  };
  const run = async (action: () => Promise<void>, failure: string) => {
    setBusy(true); setNotice(null);
    try { await action(); setChoice(null); await refresh(); notify(); }
    catch (cause) { setNotice(sandboxFailure(failure, cause)); }
    finally { setBusy(false); }
  };
  const live = envs.filter((e) => e.status !== "terminated");
  const done = envs.filter((e) => e.status === "terminated").slice(-5);

  return (
    <section aria-label="Environments" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Environments</h3>
        {!choice && <button type="button" aria-label="New environment" onClick={() => void open()}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <Plus className="h-3.5 w-3.5" aria-hidden /> New environment</button>}
      </div>
      {notice && <p role="alert" className="text-xs text-destructive">{notice}</p>}
      {choice && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/60 bg-card/20 p-3">
          <select aria-label="Profile" className={FIELD} value={choice.profile} onChange={(e) => setChoice({ ...choice, profile: e.target.value })}>
            <option value="">Default environment</option>{choice.profiles.map((p) => <option key={p} value={p}>{p}</option>)}</select>
          <select aria-label="Device preset" className={FIELD} value={choice.preset} onChange={(e) => setChoice({ ...choice, preset: e.target.value })}>
            <option value="">No device preset</option>{choice.presets.map((p) => <option key={p} value={p}>{p}</option>)}</select>
          <button type="button" disabled={busy} onClick={() => void run(() => provision({
            ...(choice.profile ? { profile: choice.profile } : {}), ...(choice.preset ? { device_preset: choice.preset } : {}) }), "Environment could not be provisioned.")}
            className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">Provision</button>
          <button type="button" onClick={() => setChoice(null)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
        </div>
      )}
      {loaded && envs.length === 0 && !choice && !notice && (
        <EmptyState icon={Box} title="No environments yet" hint="Provision one to run a target or a workload in isolation." />
      )}
      {[...live, ...done].map((e) => (
        <div key={e.env_id} className={cn("flex items-center gap-3 rounded-xl border border-border/60 bg-card/20 px-4 py-3", e.status === "terminated" && "opacity-50")}>
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-sm font-semibold">{e.env_id}</p>
            <p className="truncate text-xs text-muted-foreground">{[e.profile ?? e.instance_type, e.public_ip].filter(Boolean).join(" · ")}</p>
          </div>
          <span className={cn("rounded-full px-2 py-0.5 text-[10px]", STATUS[e.status] ?? "bg-muted/40 text-muted-foreground")}>{e.status}</span>
          {e.status !== "terminated" && (
            <ConfirmDelete label={`Terminate environment ${e.env_id}`} disabled={busy} onConfirm={() => void run(() => terminate(e.env_id), "Environment could not be terminated.")}
              className="rounded-md p-1.5 text-muted-foreground hover:text-destructive"><Power className="h-3.5 w-3.5" /></ConfirmDelete>
          )}
        </div>
      ))}
    </section>
  );
}
