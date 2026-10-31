"use client";
import { useRef, useState } from "react";
import { Download, Upload } from "lucide-react";
import { exportPreferences, importPreferences, type PreferenceSnapshot } from "./preference-backup-api";

/** Row 102 (feature-map): "host-side backup of the browser-held
 * settings ... so they survive a moved dashboard port or a relocated
 * Electron userData." Downloads/uploads a plain JSON file — the file
 * itself IS the host-side backup; nothing is stored server-side beyond
 * the durable preference record these tools already read/write. */
/** jsdom (this project's test environment) does not implement
 * ``File.prototype.text()`` — ``FileReader`` works everywhere, real
 * browser and test, so use it uniformly rather than branching by env. */
function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Couldn’t read this file."));
    reader.readAsText(file);
  });
}

export default function PreferenceBackupPanel() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"export" | "import" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = async () => {
    setBusy("export"); setError(null); setNotice(null);
    try {
      const snapshot = await exportPreferences();
      const blob = new Blob([JSON.stringify(snapshot, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = "companion-x-preferences.json";
      link.click();
      URL.revokeObjectURL(url);
      setNotice("Preferences downloaded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn’t export preferences.");
    } finally { setBusy(null); }
  };

  const upload = async (file: File) => {
    setBusy("import"); setError(null); setNotice(null);
    try {
      const text = await readFileAsText(file);
      const snapshot = JSON.parse(text) as PreferenceSnapshot;
      await importPreferences(snapshot);
      setNotice("Preferences restored. Reload to see every change.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Couldn’t restore this file.");
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  return <section aria-labelledby="preference-backup-title" className="mt-6 border-t border-border/40 pt-5">
    <h3 id="preference-backup-title" className="text-sm font-semibold">Back up your preferences</h3>
    <p className="mt-0.5 text-xs text-muted-foreground">
      Download your Chat, Display, and Shortcuts settings as a file you keep — restore them on this or any
      other Companion X dashboard. This does not include memory, lessons, or schedules (use Export a backup above).
    </p>
    {error && <p role="alert" className="mt-3 rounded-md border border-destructive/30 p-3 text-xs text-destructive">{error}</p>}
    {notice && <p role="status" className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3 text-xs text-emerald-200">{notice}</p>}
    <div className="mt-3 flex gap-2">
      <button type="button" onClick={() => void download()} disabled={busy !== null}
        className="inline-flex items-center gap-2 rounded-md border border-border/60 px-3 py-2 text-xs disabled:opacity-40">
        <Download className="h-3.5 w-3.5" />{busy === "export" ? "Downloading…" : "Download preferences"}</button>
      <label className="inline-flex items-center gap-2 rounded-md bg-violet-500 px-3 py-2 text-xs text-white cursor-pointer disabled:opacity-40 aria-disabled:opacity-40">
        <Upload className="h-3.5 w-3.5" />{busy === "import" ? "Restoring…" : "Restore from file"}
        <input ref={fileInput} type="file" accept="application/json" className="hidden" disabled={busy !== null}
          onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} />
      </label>
    </div>
  </section>;
}
