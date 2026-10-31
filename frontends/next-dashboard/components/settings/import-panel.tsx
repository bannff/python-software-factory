"use client";
import { useState } from "react";
import { Import, RefreshCw } from "lucide-react";
import { useMcpConnection } from "@/lib/hooks/use-mcp-connection";
import ExportPanel from "./export-panel";
import BundleImportPanel from "./bundle-import-panel";
import PreferenceBackupPanel from "./preference-backup-panel";
import {
  getMigration, MIGRATION_KINDS, previewMigration, startMigration,
  type MigrationKind, type MigrationPreview, type MigrationRun,
} from "./import-api";

const LABELS: Record<string, string> = {
  memory: "Memory", lessons: "Lessons", schedules: "Schedules", markdown: "Preferences, projects & history",
};

export default function ImportPanel() {
  const { ready, status } = useMcpConnection();
  const [kinds, setKinds] = useState<MigrationKind[]>([...MIGRATION_KINDS]);
  const [preview, setPreview] = useState<MigrationPreview | null>(null);
  const [run, setRun] = useState<MigrationRun | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<"preview" | "start" | "refresh" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = (kind: MigrationKind) => {
    setKinds((current) => current.includes(kind)
      ? current.filter((item) => item !== kind) : [...current, kind]);
    setPreview(null); setRun(null); setConfirmed(false); setError(null);
  };
  const inspect = async () => {
    setBusy("preview"); setError(null); setRun(null); setConfirmed(false);
    try { setPreview(await previewMigration(kinds)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Import preview unavailable."); }
    finally { setBusy(null); }
  };
  const start = async () => {
    if (!preview) return;
    setBusy("start"); setError(null);
    try {
      const started = await startMigration(preview, kinds); setRun(started);
      try { setRun(await getMigration(started.runId)); }
      catch (cause) { setError(cause instanceof Error ? cause.message : "Progress is not ready yet."); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Import could not start."); }
    finally { setBusy(null); }
  };
  const refresh = async () => {
    if (!run) return;
    setBusy("refresh"); setError(null);
    try { setRun(await getMigration(run.runId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Progress unavailable."); }
    finally { setBusy(null); }
  };
  const eligible = preview?.reports.reduce((total, report) => total + report.eligible, 0) ?? 0;

  return <section aria-labelledby="import-settings-title" className="rounded-lg border border-border/50 bg-card/30 p-5">
    <h2 id="import-settings-title" className="text-sm font-semibold">Import & Export</h2>
    <p className="mt-0.5 text-xs text-muted-foreground">Bring supported KiroCrew data into Companion X.</p>
    <div className="mt-4 rounded-md border border-border/40 bg-muted/20 p-4">
      <p className="text-sm font-medium">Merge-only import</p>
      <p className="mt-1 text-xs text-muted-foreground">Adds missing items only. It never overwrites or deletes existing Companion X data. Schedules arrive paused.</p>
    </div>
    <fieldset className="mt-4"><legend className="text-xs font-medium">Data to import</legend>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">{MIGRATION_KINDS.map((kind) => <label key={kind}
        className="flex items-center gap-2 rounded-md border border-border/40 px-3 py-2 text-xs">
        <input type="checkbox" checked={kinds.includes(kind)} onChange={() => toggle(kind)} />{LABELS[kind]}</label>)}</div>
    </fieldset>
    {!ready && <p className="mt-4 text-xs text-muted-foreground">MCP is {status}.</p>}
    {error && <p role="alert" className="mt-4 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
    <button type="button" onClick={() => void inspect()} disabled={!ready || kinds.length === 0 || busy !== null}
      className="mt-4 rounded-md border border-border/60 px-3 py-2 text-xs disabled:opacity-40">
      {busy === "preview" ? "Building preview…" : "Preview import"}</button>

    {preview && <div className="mt-5 border-t border-border/40 pt-4">
      <div className="flex items-center justify-between gap-3"><div><h3 className="text-sm font-semibold">Preview</h3>
        <p className="text-xs text-muted-foreground">{eligible} eligible items in this immutable plan</p></div>
        <span className="rounded-full bg-violet-500/10 px-2 py-1 text-[10px] text-violet-300">{preview.status}</span></div>
      <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-muted-foreground"><tr>
        <th className="py-2">Type</th><th>Found</th><th>Eligible</th><th>Excluded</th></tr></thead><tbody>
        {preview.reports.map((report) => <tr key={report.kind} className="border-t border-border/30"><td className="py-2">{LABELS[report.kind] ?? report.kind}</td>
          <td>{report.found}</td><td>{report.eligible}</td><td>{report.excluded}</td></tr>)}</tbody></table></div>
      {preview.samples.length > 0 && <details className="mt-3 rounded-md border border-border/40 p-3"><summary className="cursor-pointer text-xs font-medium">Redacted samples</summary>
        <ul className="mt-2 grid gap-2">{preview.samples.map((sample, index) => <li key={`${sample.kind}-${index}`} className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">{LABELS[sample.kind] ?? sample.kind}:</span> {sample.sample}</li>)}</ul></details>}
      {!run && <><label className="mt-4 flex items-start gap-2 text-xs"><input type="checkbox" checked={confirmed}
        onChange={(event) => setConfirmed(event.target.checked)} /><span>I reviewed this preview and want to import these eligible items.</span></label>
        <button type="button" onClick={() => void start()} disabled={!confirmed || eligible === 0 || busy !== null}
          className="mt-3 inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
          <Import className="h-3.5 w-3.5" />{busy === "start" ? "Starting…" : "Start merge-only import"}</button></>}
    </div>}

    {run && <div className="mt-5 rounded-md border border-border/50 p-4" aria-live="polite">
      <div className="flex items-center justify-between gap-3"><div><h3 className="text-sm font-semibold">Import {run.status}</h3>
        <p className="text-[10px] text-muted-foreground">Run {run.runId}</p></div>
        <button type="button" aria-label="Refresh import progress" onClick={() => void refresh()} disabled={busy !== null}
          className="rounded-md border p-2 disabled:opacity-40"><RefreshCw className={`h-4 w-4 ${busy === "refresh" ? "animate-spin" : ""}`} /></button></div>
      {run.progress.length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2">{run.progress.map((item) => <div key={item.kind} className="rounded-md bg-muted/20 p-3 text-xs">
        <p className="font-medium">{LABELS[item.kind] ?? item.kind}</p><p className="mt-1 text-muted-foreground">{item.imported} imported · {item.skipped} skipped · {item.failed} failed</p></div>)}</div>}
      {run.terminalReason && <p className="mt-3 text-xs text-muted-foreground">Finished: {run.terminalReason}</p>}
    </div>}
    <ExportPanel />
    <BundleImportPanel />
    <PreferenceBackupPanel />
  </section>;
}
