"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Plus, Terminal, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDisplayPreferences } from "@/components/settings/use-display-preferences";
import {
  closeTerminalSession, listTerminalSessions, listTerminalShells, openTerminalSession,
} from "@/lib/terminal-api";
import { terminalScope } from "@/lib/terminal-session-store";
import {
  disposeConnection, type TerminalConnectionStatus,
} from "@/lib/terminal-connection-registry";
import { useTerminalMount } from "@/lib/hooks/use-terminal-session";
import { TerminalCompletion } from "./terminal-completion";

let automaticOpen: ReturnType<typeof openTerminalSession> | null = null;

function openAutomaticSession(shell?: string) {
  if (!automaticOpen) {
    automaticOpen = openTerminalSession(shell ? { shell } : {})
      .finally(() => { automaticOpen = null; });
  }
  return automaticOpen;
}
export function TerminalPanel({ onClose }: { onClose: () => void }) {
  const { preferences: display, loading: displayLoading } = useDisplayPreferences();
  const scope = terminalScope;
  const sessions = useSyncExternalStore(scope.subscribe, scope.getSessions, scope.getSessions);
  const active = useSyncExternalStore(scope.subscribe, scope.getActive, scope.getActive);
  const [shells, setShells] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] =
    useState<TerminalConnectionStatus | null>(null);
  const [reconciled, setReconciled] = useState(false);
  const autoOpenStarted = useRef(false);
  const [container, handle] = useTerminalMount(
    reconciled ? active : null, display.terminalFontSize, {
      onSession: (session) => scope.upsert(session),
      onDead: (sessionId) => scope.remove(sessionId),
    },
  );

  useEffect(() => { void listTerminalShells().then((r) => setShells(r.shells)).catch(() => {}); }, []);

  // Server-authoritative rehydration: drop persisted ids the backend no longer
  // reports alive, then allow auto-open to evaluate against the real set.
  useEffect(() => {
    autoOpenStarted.current = false;
    setReconciled(false);
    let cancelled = false;
    void (async () => {
      try {
        const live = await listTerminalSessions();
        if (!cancelled) scope.reconcile(new Set(live.sessions.map((s) => s.session_id)));
      } catch { /* backend unavailable — keep persisted set optimistically */ }
      if (!cancelled) setReconciled(true);
    })();
    return () => { cancelled = true; };
  }, [scope]);

  useEffect(() => {
    if (!reconciled || displayLoading) return;
    if (sessions.length > 0) {
      autoOpenStarted.current = true;
      return;
    }
    if (autoOpenStarted.current) return;
    autoOpenStarted.current = true;
    void openAutomaticSession(display.terminalShell ?? undefined)
      .then(({ session }) => {
        scope.upsert(session);
        scope.setActive(session.session_id);
      })
      .catch(() => setError("Terminal is unavailable."));
  }, [reconciled, displayLoading, display.terminalShell, sessions.length, scope]);

  useEffect(() => { if (handle) handle.term.options.fontSize = display.terminalFontSize; }, [handle, display.terminalFontSize]);
  useEffect(() => {
    if (!handle) { setConnectionStatus(null); return; }
    const sync = () => setConnectionStatus(handle.getStatus());
    sync();
    return handle.subscribe(sync);
  }, [handle]);

  const openSession = async (shell?: string) => {
    setError(null);
    try {
      const spec = shell ? { shell } : {};
      const { session } = await openTerminalSession(spec);
      scope.upsert(session);
      scope.setActive(session.session_id);
    } catch { setError("Terminal is unavailable."); }
  };

  const closeSession = async (sessionId: string) => {
    scope.remove(sessionId);
    disposeConnection(sessionId);
    try { await closeTerminalSession(sessionId); } catch { /* best-effort */ }
  };

  return (
    <section aria-label="Terminal panel"
      className="flex h-56 shrink-0 flex-col border-t border-border/60 bg-[#070a12]">
      <header className="flex h-9 shrink-0 items-center border-b border-border/50 px-2">
        <div className="flex items-center gap-1.5 px-2 text-xs font-medium"><Terminal className="h-3.5 w-3.5" /> Terminal</div>
        <div role="tablist" aria-label="Terminal sessions" className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto px-2">
          {sessions.map((session) => (
            <div key={session.session_id} className="group flex shrink-0 items-center">
              <button type="button" role="tab" aria-selected={active === session.session_id}
                onClick={() => scope.setActive(session.session_id)}
                className={cn("max-w-40 truncate rounded px-2 py-1 font-mono text-[10px]",
                  active === session.session_id ? "bg-violet-500/15 text-violet-300" : "text-muted-foreground hover:bg-accent/30")}
                title={session.shell}>{session.shell.split("/").pop()}</button>
              <button type="button" aria-label={`Close ${session.shell} session`}
                onClick={() => void closeSession(session.session_id)}
                className="rounded p-0.5 text-muted-foreground opacity-0 hover:text-foreground group-hover:opacity-100">
                <X className="h-3 w-3" /></button>
            </div>
          ))}
          <label className="shrink-0 text-[10px]">
            <span className="sr-only">Open shell</span>
            <select aria-label="Open shell" value="" onChange={(e) => { if (e.target.value) void openSession(e.target.value); }}
              className="rounded bg-transparent px-1 py-1 text-muted-foreground hover:text-foreground">
              <option value="">＋ shell…</option>
              {shells.map((shell) => <option key={shell} value={shell}>{shell}</option>)}
            </select>
          </label>
          <button type="button" aria-label="New terminal session" onClick={() => void openSession()}
            className="rounded p-1 text-muted-foreground hover:bg-accent/30 hover:text-foreground">
            <Plus className="h-3 w-3" /></button>
        </div>
        <button type="button" onClick={onClose} aria-label="Close Terminal"
          className="rounded p-1.5 text-muted-foreground hover:bg-accent/40 hover:text-foreground"><X className="h-3.5 w-3.5" /></button>
      </header>
      {error && <p role="alert" className="px-3 py-1 text-[10px] text-destructive">{error}</p>}
      {(connectionStatus === "displaced" || connectionStatus === "disconnected") && handle && (
        <p role="alert" className="flex items-center gap-2 px-3 py-1 text-[10px] text-muted-foreground">
          <span>{connectionStatus === "displaced" ? "Terminal opened elsewhere." : "Terminal disconnected."}</span>
          <button type="button" className="underline" onClick={() => void handle.reconnect().catch(() => {})}>
            Reconnect
          </button>
        </p>
      )}
      <div role="tabpanel" className="relative min-h-0 flex-1 p-1">
        <div ref={container} className="h-full min-h-0" />
        {handle && active && <TerminalCompletion
          term={handle.term} sessionId={active} active
          enabled={display.terminalCompletionEnabled} send={handle.send}
        />}
      </div>
    </section>
  );
}
