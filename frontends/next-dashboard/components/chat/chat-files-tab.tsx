"use client";

import { useCallback, useEffect, useState } from "react";
import { File as FileIcon, Folder, ChevronUp } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Row 24 (feature-map) — Files in chat, homed in the chat side panel.
 * Browses the workspace via the existing `devtools_list_dir` MCP read and
 * lets you insert a file reference into the composer. Scaffold: browse +
 * reference-insert ship; upload and inline attachment previews are deferred.
 */
interface Entry { path: string; kind: string }

function parentDir(path: string): string {
  if (path === "." || path === "") return ".";
  const idx = path.lastIndexOf("/");
  return idx <= 0 ? "." : path.slice(0, idx);
}

export function ChatFilesTab({ onInsert }: { onInsert: (reference: string) => void }) {
  const [cwd, setCwd] = useState(".");
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (path: string) => {
    setError(null);
    try {
      const data = unwrapToolData(await callTool("devtools_list_dir", { path })) as
        { result?: { entries?: Entry[] } } | null;
      setEntries(data?.result?.entries ?? []);
    } catch {
      setError("Couldn’t list this directory.");
      setEntries([]);
    }
  }, []);

  useEffect(() => { void load(cwd); }, [cwd, load]);

  const isDir = (kind: string) => kind === "dir" || kind === "directory";

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <button type="button" aria-label="Up one directory" disabled={cwd === "."}
          onClick={() => setCwd(parentDir(cwd))}
          className="rounded-md p-1 hover:bg-accent/40 disabled:opacity-30"><ChevronUp className="h-3.5 w-3.5" /></button>
        <span className="truncate" title={cwd}>{cwd === "." ? "workspace" : cwd}</span>
      </div>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {entries && entries.length === 0 && !error && (
        <p className="text-sm italic text-muted-foreground/70">Empty directory.</p>
      )}
      {entries?.map((entry) => (
        isDir(entry.kind) ? (
          <button key={entry.path} type="button" onClick={() => setCwd(entry.path)}
            className="flex items-center gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-muted/40">
            <Folder className="h-3.5 w-3.5 shrink-0 text-amber-300" />
            <span className="truncate">{entry.path.split("/").pop()}</span>
          </button>
        ) : (
          <button key={entry.path} type="button" aria-label={`Reference ${entry.path}`}
            onClick={() => onInsert(`@${entry.path} `)}
            className="flex items-center gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-muted/40">
            <FileIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate">{entry.path.split("/").pop()}</span>
          </button>
        )
      ))}
    </div>
  );
}
