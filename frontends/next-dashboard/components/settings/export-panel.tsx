"use client";
import { useState } from "react";
import { Download } from "lucide-react";
import { EXPORT_KINDS, previewExport, runExport, type ExportKind, type ExportPreview, type ExportResult } from "./export-api";

const LABELS: Record<ExportKind, string> = {
  memory: "Export memory", kb: "Export knowledge base", lessons: "Export lessons",
  schedules: "Export schedules", preferences: "Export display preferences",
};

export default function ExportPanel() {
  const [kinds, setKinds] = useState<ExportKind[]>([...EXPORT_KINDS]);
  const [name, setName] = useState("backup.cxbundle.json");
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [busy, setBusy] = useState<"preview" | "export" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = (kind: ExportKind) => {
    setKinds((current) => current.includes(kind)
      ? current.filter((item) => item !== kind) : [...current, kind]);
    setPreview(null); setResult(null); setError(null);
  };
  const inspect = async () => {
    setBusy("preview"); setError(null); setResult(null);
    try { setPreview(await previewExport(kinds)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Export preview unavailable."); }
    finally { setBusy(null); }
  };
  const write = async () => {
    setBusy("export"); setError(null);
    try { setResult(await runExport(name, kinds)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Export could not be written."); }
    finally { setBusy(null); }
  };

  return <section aria-labelledby="export-settings-title" className="mt-6 border-t border-border/40 pt-5">
    <h3 id="export-settings-title" className="text-sm font-semibold">Export a backup</h3>
    <p className="mt-0.5 text-xs text-muted-foreground">Write your own memory, lessons, schedules, and preferences to a file you can re-import later — never overwrites existing data on import, never includes secrets.</p>
    <fieldset className="mt-3"><legend className="text-xs font-medium">Data to export</legend>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">{EXPORT_KINDS.map((kind) => <label key={kind}
        className="flex items-center gap-2 rounded-md border border-border/40 px-3 py-2 text-xs">
        <input type="checkbox" checked={kinds.includes(kind)} onChange={() => toggle(kind)} />{LABELS[kind]}</label>)}</div>
    </fieldset>
    <label className="mt-3 block text-xs"><span className="font-medium">File name</span>
      <input type="text" value={name} onChange={(event) => setName(event.target.value)}
        className="mt-1 block w-full rounded-md border border-border/40 bg-transparent px-3 py-2 text-xs" /></label>
    {error && <p role="alert" className="mt-3 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
    <div className="mt-3 flex gap-2">
      <button type="button" onClick={() => void inspect()} disabled={kinds.length === 0 || busy !== null}
        className="rounded-md border border-border/60 px-3 py-2 text-xs disabled:opacity-40">
        {busy === "preview" ? "Building preview…" : "Preview export"}</button>
      {preview && <button type="button" onClick={() => void write()} disabled={!name.trim() || busy !== null}
        className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">
        <Download className="h-3.5 w-3.5" />{busy === "export" ? "Writing…" : "Write backup file"}</button>}
    </div>
    {preview && !result && <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-muted-foreground"><tr>
      <th className="py-2">Type</th><th>Count</th><th>Excluded</th></tr></thead><tbody>
      {preview.kinds.map((item) => <tr key={item.kind} className="border-t border-border/30"><td className="py-2">{LABELS[item.kind as ExportKind] ?? item.kind}</td>
        <td>{item.count}</td><td>{item.excluded}</td></tr>)}</tbody></table></div>}
    {result && <p className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs text-emerald-200">
      Wrote {result.bytesWritten.toLocaleString()} bytes to {result.path}.</p>}
  </section>;
}
