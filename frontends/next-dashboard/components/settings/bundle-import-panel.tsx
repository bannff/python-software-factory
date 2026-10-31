"use client";
import { useState } from "react";
import { Upload, RefreshCw } from "lucide-react";
import {
  getMigration, startMigration, type MigrationRun,
} from "./import-api";
import { previewBundleImport, type BundlePreview } from "./export-api";

const LABELS: Record<string, string> = {
  memory: "Memory", lessons: "Lessons", schedules: "Schedules",
  kb: "Knowledge base", preferences: "Display preferences",
};

export default function BundleImportPanel() {
  const [bundleRef, setBundleRef] = useState("backup.cxbundle.json");
  const [preview, setPreview] = useState<BundlePreview | null>(null);
  const [run, setRun] = useState<MigrationRun | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<"preview" | "start" | "refresh" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inspect = async () => {
    setBusy("preview"); setError(null); setPreview(null); setRun(null); setConfirmed(false);
    try { setPreview(await previewBundleImport(bundleRef)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Bundle preview unavailable."); }
    finally { setBusy(null); }
  };
  const start = async () => {
    if (!preview) return;
    setBusy("start"); setError(null);
    try {
      const kinds = preview.reports.map((report) => report.kind);
      const started = await startMigration({ planDigest: preview.planDigest }, kinds, "companion-x-v1");
      setRun(started);
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

  return <section aria-labelledby="bundle-import-title" className="mt-6 border-t border-border/40 pt-5">
    <h3 id="bundle-import-title" className="text-sm font-semibold">Restore from a backup</h3>
    <p className="mt-0.5 text-xs text-muted-foreground">Re-import a bundle written by Export a backup. Merge-only — never overwrites existing Companion X data.</p>
    <label className="mt-3 block text-xs"><span className="font-medium">Backup file name</span>
      <input type="text" value={bundleRef} onChange={(event) => setBundleRef(event.target.value)}
        className="mt-1 block w-full rounded-md border border-border/40 bg-transparent px-3 py-2 text-xs" /></label>
    {error && <p role="alert" className="mt-3 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
    <button type="button" onClick={() => void inspect()} disabled={!bundleRef.trim() || busy !== null}
      className="mt-3 rounded-md border border-border/60 px-3 py-2 text-xs disabled:opacity-40">
      {busy === "preview" ? "Reading bundle…" : "Preview restore"}</button>

    {preview && !run && <div className="mt-4">
      <p className="text-xs text-muted-foreground">{eligible} eligible items in this immutable plan</p>
      <div className="mt-2 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-muted-foreground"><tr>
        <th className="py-2">Type</th><th>Found</th><th>Eligible</th><th>Excluded</th></tr></thead><tbody>
        {preview.reports.map((report) => <tr key={report.kind} className="border-t border-border/30"><td className="py-2">{LABELS[report.kind] ?? report.kind}</td>
          <td>{report.found}</td><td>{report.eligible}</td><td>{report.excluded}</td></tr>)}</tbody></table></div>
      {preview.unsupportedKinds.length > 0 && <p className="mt-2 text-[11px] text-amber-300">
        {preview.unsupportedKinds.map((k) => LABELS[k] ?? k).join(", ")} cannot be restored yet — no import target exists for those kinds.</p>}
      <label className="mt-3 flex items-start gap-2 text-xs"><input type="checkbox" checked={confirmed}
        onChange={(event) => setConfirmed(event.target.checked)} /><span>I reviewed this preview and want to restore these eligible items.</span></label>
      <button type="button" onClick={() => void start()} disabled={!confirmed || eligible === 0 || busy !== null}
        className="mt-3 inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
        <Upload className="h-3.5 w-3.5" />{busy === "start" ? "Starting…" : "Start merge-only restore"}</button>
    </div>}

    {run && <div className="mt-4 rounded-md border border-border/50 p-4" aria-live="polite">
      <div className="flex items-center justify-between gap-3"><div><p className="text-sm font-semibold">Restore {run.status}</p>
        <p className="text-[10px] text-muted-foreground">Run {run.runId}</p></div>
        <button type="button" aria-label="Refresh restore progress" onClick={() => void refresh()} disabled={busy !== null}
          className="rounded-md border p-2 disabled:opacity-40"><RefreshCw className={`h-4 w-4 ${busy === "refresh" ? "animate-spin" : ""}`} /></button></div>
      {run.progress.length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2">{run.progress.map((item) => <div key={item.kind} className="rounded-md bg-muted/20 p-3 text-xs">
        <p className="font-medium">{LABELS[item.kind] ?? item.kind}</p><p className="mt-1 text-muted-foreground">{item.imported} imported · {item.skipped} skipped · {item.failed} failed</p></div>)}</div>}
      {run.terminalReason && <p className="mt-3 text-xs text-muted-foreground">Finished: {run.terminalReason}</p>}
    </div>}
  </section>;
}
