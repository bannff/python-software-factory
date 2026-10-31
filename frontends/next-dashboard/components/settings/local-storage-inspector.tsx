"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";

/**
 * Row 107 (feature-map) — raw localStorage inspector, homed in Settings →
 * Developer. Client-only (upstream's own `LocalStorageDebug` has no
 * handler): lists the browser's localStorage keys with a value preview,
 * refresh, and per-key delete. A read/prune diagnostic, not a data manager.
 */
interface Entry { key: string; value: string }

function readAll(): Entry[] {
  if (typeof window === "undefined" || !window.localStorage) return [];
  const entries: Entry[] = [];
  for (let i = 0; i < window.localStorage.length; i++) {
    const key = window.localStorage.key(i);
    if (key === null) continue;
    entries.push({ key, value: window.localStorage.getItem(key) ?? "" });
  }
  return entries.sort((a, b) => a.key.localeCompare(b.key));
}

export function LocalStorageInspector() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const refresh = useCallback(() => setEntries(readAll()), []);
  useEffect(() => { refresh(); }, [refresh]);

  const remove = (key: string) => {
    window.localStorage.removeItem(key);
    refresh();
  };

  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">Local storage</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Inspect and prune this browser’s stored keys ({entries.length}). Nothing here syncs to the server.
          </p>
        </div>
        <button type="button" aria-label="Refresh local storage" onClick={refresh}
          className="rounded-md border border-border/60 p-1.5 text-muted-foreground hover:bg-muted/50 hover:text-foreground">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      {entries.length === 0 ? (
        <p className="mt-3 text-xs italic text-muted-foreground/70">No keys stored.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-1">
          {entries.map((entry) => (
            <li key={entry.key} className="flex items-start gap-2 rounded-md border border-border/40 bg-muted/10 p-2">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium text-foreground" title={entry.key}>{entry.key}</span>
                <span className="mt-0.5 block truncate text-[11px] text-muted-foreground" title={entry.value}>{entry.value || "—"}</span>
              </span>
              <button type="button" aria-label={`Delete ${entry.key}`} onClick={() => remove(entry.key)}
                className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
