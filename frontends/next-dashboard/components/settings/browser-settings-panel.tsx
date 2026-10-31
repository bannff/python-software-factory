"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, Globe, Loader2, PlayCircle, ShieldCheck } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

interface EngineStatus {
  engine: string; availableEngines: string[]; chromePath: string | null;
  chromeFound: boolean; websocketsAvailable: boolean; changeHint: string;
}
interface Smoke { ok: boolean; browserType: string | null; error: string | null; elapsedMs: number }

function statusFrom(raw: unknown): EngineStatus {
  const v = unwrapToolData(raw) as Record<string, unknown>;
  if (typeof v.engine !== "string" || !Array.isArray(v.available_engines)) throw new Error("Engine status unavailable.");
  return {
    engine: v.engine, availableEngines: v.available_engines.filter((e): e is string => typeof e === "string"),
    chromePath: typeof v.chrome_path === "string" ? v.chrome_path : null, chromeFound: v.chrome_found === true,
    websocketsAvailable: v.websockets_available === true, changeHint: typeof v.change_hint === "string" ? v.change_hint : "",
  };
}

/**
 * Settings → Browser. The engine is a process-wide composition choice
 * (`FACTORY_BROWSER_ADAPTER`), so this page reports the EFFECTIVE engine and
 * its readiness truthfully and says how to change it — it does not pretend a
 * per-owner toggle could switch a global adapter.
 */
export default function BrowserSettingsPanel() {
  const [status, setStatus] = useState<EngineStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [smoke, setSmoke] = useState<Smoke | null>(null);
  const [testing, setTesting] = useState(false);

  const refresh = useCallback(async () => {
    try { setStatus(statusFrom(await callTool("browser_get_engine_status"))); setError(null); }
    catch { setError("Engine status unavailable."); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const runSmoke = async () => {
    setTesting(true); setSmoke(null);
    try {
      const v = unwrapToolData(await callTool("browser_engine_smoke")) as Record<string, unknown>;
      setSmoke({ ok: v.ok === true, browserType: typeof v.browser_type === "string" ? v.browser_type : null,
        error: typeof v.error === "string" ? v.error : null, elapsedMs: typeof v.elapsed_ms === "number" ? v.elapsed_ms : 0 });
    } catch (cause) { setSmoke({ ok: false, browserType: null, error: cause instanceof Error ? cause.message : "Smoke test failed.", elapsedMs: 0 }); }
    finally { setTesting(false); }
  };

  const real = status?.engine === "cdp";
  return <section aria-labelledby="browser-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="browser-settings-title" className="text-sm font-semibold">Browser</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">The engine your agents' browser tools run on.</p>
    {error && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
    {status && <div className="mt-4 rounded-md border border-border/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-[10px] font-medium uppercase tracking-wider text-violet-300">Engine</p>
          <p className="mt-0.5 text-sm font-medium">{real ? "System Chrome (CDP)" : "Mock — no real browser"}</p>
          {!real && <p className="mt-1 text-xs text-amber-400">Agents' browser tools return placeholder results until the engine is set to CDP.</p>}</div>
        <button type="button" onClick={() => void runSmoke()} disabled={testing}
          className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-50">
          {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="h-3.5 w-3.5" />} Test engine</button>
      </div>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
        <Row label="Chrome" value={status.chromeFound ? status.chromePath ?? "found" : "not found"} ok={status.chromeFound} />
        <Row label="CDP transport" value={status.websocketsAvailable ? "available" : "websockets missing"} ok={status.websocketsAvailable} />
        <Row label="Engines" value={status.availableEngines.join(" · ")} ok />
      </dl>
      {smoke && <p role="status" className={`mt-3 text-xs ${smoke.ok ? "text-emerald-400" : "text-destructive"}`}>
        {smoke.ok ? `Launched and closed a ${smoke.browserType} session in ${smoke.elapsedMs} ms.` : `Engine test failed: ${smoke.error}`}</p>}
      <p className="mt-3 text-[11px] text-muted-foreground">To change the engine: {status.changeHint}</p>
    </div>}
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <article className="rounded-md border border-border/40 p-4"><Globe className="h-5 w-5 text-violet-400" />
        <h3 className="mt-3 text-sm font-medium">Browser tools</h3>
        <p className="mt-1 text-xs text-muted-foreground">Launch, navigate, read content, interact, and screenshot — listed under Connections → browser.</p>
        <a href="/capabilities?tab=connections" className="mt-3 inline-flex items-center gap-2 text-xs font-medium text-violet-300 hover:text-violet-200">Open Connections<ArrowUpRight className="h-3.5 w-3.5" /></a></article>
      <article className="rounded-md border border-border/40 p-4"><ShieldCheck className="h-5 w-5 text-violet-400" />
        <h3 className="mt-3 text-sm font-medium">Interactive page control</h3>
        <p className="mt-1 text-xs text-muted-foreground">Use the Globe control in the dashboard Browser panel to allow interaction for this session.</p></article>
    </div>
    <p className="mt-4 rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">
      Not applicable here: installing Playwright (Companion X drives the system Chrome via CDP) and attaching a hosted-engine token (there is no hosted engine).
    </p>
  </section>;
}

function Row({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return <div className="rounded-md border border-border/30 px-3 py-2">
    <dt className="text-[10px] text-muted-foreground">{label}</dt>
    <dd className={`m-0 truncate font-mono text-[11px] ${ok ? "text-foreground/90" : "text-amber-400"}`} title={value}>{value}</dd>
  </div>;
}
