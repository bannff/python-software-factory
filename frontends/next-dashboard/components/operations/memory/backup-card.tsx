"use client";

import { useRef, useState } from "react";
import { AlertTriangle, Download, HardDriveDownload, Loader2, Upload } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/** ``File.text()`` — real in every shipping browser — is not implemented
 * by this project's jsdom test environment (`node_modules/jsdom` lacks
 * ``File.prototype.text``, confirmed directly before switching). Read via
 * ``FileReader`` instead: works identically in real browsers AND in this
 * test environment, so the component and its tests exercise the same code. */
function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

// Matches backup_models.py's PAGE_CHUNK_CHARS — how the base64 string is
// re-split into pages on import. Export pages come pre-sliced from the
// server at this same size, so import re-slices identically for symmetry.
const IMPORT_PAGE_CHUNK_CHARS = 8 * 1024 * 1024;

/**
 * Row 48 (Backups) — owner direction 2026-09-16: "simple export/import of
 * the whole graph to one file; no staged-restore-on-restart ceremony."
 * Export downloads one JSON file immediately; import applies immediately
 * on confirm (arm-then-confirm, since it REPLACES the whole shared graph
 * that both Memory and Knowledge Base read from — this is not a per-user
 * memory backup, it is the whole store).
 *
 * **Paged (fixed 2026-09-16):** the owner's real graph serializes to
 * ~51 MB of base64 — well over the 16 MiB typed-egress cap a single MCP
 * call enforces. Export re-fetches `graph_export` page by page (the
 * server slices and caches the encoded string); import re-slices the
 * chosen file's text into pages and sends them via
 * `graph_import_begin` → repeated `graph_import_page` calls, applying
 * only once the server has every page.
 */
export default function BackupCard() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [armedFile, setArmedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const onExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const chunks: string[] = [];
      let page = 0;
      let pageCount = 1;
      let supported = true;
      for (;;) {
        const raw = await callTool("graph_export", { page });
        const data = unwrapToolData(raw) as {
          supported?: boolean; data_base64?: string; page_count?: number; done?: boolean;
        };
        if (data.supported === false) {
          supported = false;
          break;
        }
        chunks.push(data.data_base64 ?? "");
        pageCount = data.page_count ?? 1;
        if (data.done !== false) break;
        page += 1;
        if (page >= pageCount) break; // guard against a malformed done flag
      }
      if (!supported || chunks.every((c) => c.length === 0)) {
        setError("This backend has nothing exportable.");
        return;
      }
      const bytes = atob(chunks.join(""));
      const blob = new Blob([bytes], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `companion-x-graph-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setNotice(`Graph exported (${pageCount} page${pageCount > 1 ? "s" : ""}).`);
    } catch {
      setError("Export failed.");
    } finally {
      setExporting(false);
    }
  };

  const onFileChosen = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setArmedFile(file);
    setError(null);
  };

  const onImport = async () => {
    if (!armedFile) return;
    setImporting(true);
    setError(null);
    try {
      const text = await readFileAsText(armedFile);
      const dataBase64 = btoa(text);
      const totalPages = Math.max(1, Math.ceil(dataBase64.length / IMPORT_PAGE_CHUNK_CHARS));

      const beginRaw = await callTool("graph_import_begin", { total_pages: totalPages });
      const begin = unwrapToolData(beginRaw) as { import_id?: string };
      if (!begin.import_id) {
        setError("Import could not start.");
        return;
      }

      let last: { imported?: boolean; error?: string } = {};
      for (let page = 0; page < totalPages; page += 1) {
        const start = page * IMPORT_PAGE_CHUNK_CHARS;
        const chunk = dataBase64.slice(start, start + IMPORT_PAGE_CHUNK_CHARS);
        const pageRaw = await callTool("graph_import_page", {
          import_id: begin.import_id, page, data_base64: chunk,
        });
        last = unwrapToolData(pageRaw) as { imported?: boolean; error?: string };
      }

      if (last.imported !== true) {
        setError(last.error === "backend_not_supported"
          ? "This backend does not support import."
          : "That file could not be imported — it may be corrupt.");
        return;
      }
      setNotice("Graph imported. The whole store was replaced.");
      setArmedFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch {
      setError("Import failed.");
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="rounded-lg border border-border/60 bg-card/30 p-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <HardDriveDownload className="h-4 w-4 text-violet-400" /> Backup
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Export the whole memory graph to one file, or import a file to replace it. Applies immediately.
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onExport}
          disabled={exporting}
          className="flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-2 text-xs transition-colors hover:bg-muted/50 disabled:opacity-50"
        >
          {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />} Export
        </button>

        <input ref={inputRef} type="file" accept="application/json" onChange={onFileChosen} className="hidden" id="graph-import-input" />
        <label htmlFor="graph-import-input" className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-border/60 px-3 py-2 text-xs transition-colors hover:bg-muted/50">
          <Upload className="h-3.5 w-3.5" /> Choose file…
        </label>

        {armedFile && (
          <>
            <span className="text-xs text-muted-foreground">{armedFile.name}</span>
            <button
              type="button"
              onClick={onImport}
              disabled={importing}
              className="flex items-center gap-1.5 rounded-lg border border-destructive/40 px-3 py-2 text-xs text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
            >
              {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <AlertTriangle className="h-3.5 w-3.5" />} Replace whole graph with this file
            </button>
          </>
        )}
      </div>

      {error && <p role="alert" className="mt-2 text-xs text-destructive">{error}</p>}
      {notice && !error && <p className="mt-2 text-xs text-muted-foreground">{notice}</p>}
    </div>
  );
}
