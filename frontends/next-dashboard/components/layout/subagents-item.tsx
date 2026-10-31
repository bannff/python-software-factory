"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Square, Users } from "lucide-react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import { Popover } from "@/components/ui/popover";

interface BackgroundRun {
  runId: string; personaId: string; status: string; kind: string; startedAt: string;
}

const ACTIVE = new Set(["pending", "running", "waiting"]);
const POLL_MS = 10_000;
const MAX_CONSECUTIVE_FAILURES = 3;

function parseRuns(raw: unknown): BackgroundRun[] {
  const data = unwrapToolData(raw) as Record<string, unknown>;
  const rows = Array.isArray(data.runs) ? data.runs : [];
  return rows.filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null)
    .map((r) => ({
      runId: String(r.run_id ?? ""), personaId: String(r.persona_id ?? ""),
      status: String(r.status ?? ""), kind: String(r.kind ?? ""),
      startedAt: String(r.started_at ?? ""),
    }))
    .filter((r) => r.runId);
}

/**
 * Row 80 (Subagents) rail badge + viewer. Sits in the status bar beside the
 * Terminal toggle — this popover IS the Activity Viewer; there is no
 * separate page. Backed by ``agent.list_background_runs`` (reads the
 * Workflow runs launched by ``spawn_background``/loop cycles) and
 * ``workflow.cancel_run`` for per-row Cancel + Stop All.
 */
export function SubagentsItem() {
  const [runs, setRuns] = useState<BackgroundRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const failureCount = useRef(0);

  const refresh = useCallback(async () => {
    try {
      setRuns(parseRuns(await callTool("agent.list_background_runs", {})));
      setError(null);
      setUnavailable(false);
      failureCount.current = 0;
    } catch {
      setError("Subagents unavailable");
      failureCount.current += 1;
      if (failureCount.current >= MAX_CONSECUTIVE_FAILURES) setUnavailable(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => { if (!unavailable) void refresh(); }, POLL_MS);
    return () => clearInterval(id);
  }, [refresh, unavailable]);

  const active = runs.filter((r) => ACTIVE.has(r.status));

  const cancel = async (runId: string) => {
    setBusy(runId);
    try { unwrapToolData(await callTool("workflow.cancel_run", { run_id: runId, reason: "user_cancelled" })); }
    finally { setBusy(null); await refresh(); }
  };
  const stopAll = async () => {
    for (const run of active) await cancel(run.runId);
  };

  return (
    <Popover align="right" trigger={
      <div className="flex items-center gap-1 text-muted-foreground" aria-label="Subagents">
        <Users className="h-3 w-3" /><span>{active.length}</span>
      </div>
    }>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-medium text-foreground">Subagents</span>
          {active.length > 0 && (
            <button type="button" onClick={() => void stopAll()}
              className="flex items-center gap-1 text-destructive hover:underline">
              <Square className="h-3 w-3" /> Stop all
            </button>
          )}
        </div>
        {unavailable && <p className="text-muted-foreground">Subagents unavailable right now.</p>}
        {!unavailable && error && <p className="text-destructive">{error}</p>}
        {!unavailable && !error && runs.length === 0 && <p className="text-muted-foreground">No background runs.</p>}
        <div className="max-h-[220px] space-y-1 overflow-y-auto">
          {runs.map((run) => (
            <div key={run.runId} className="flex items-center gap-2 rounded px-1.5 py-1 hover:bg-accent/30">
              <span className="min-w-0 flex-1 truncate text-foreground" title={run.runId}>{run.personaId || run.runId}</span>
              <span className="shrink-0 text-muted-foreground">{run.status}</span>
              {ACTIVE.has(run.status) && (
                <button type="button" onClick={() => void cancel(run.runId)} disabled={busy === run.runId}
                  aria-label={`Cancel ${run.runId}`} className="shrink-0 text-destructive hover:underline disabled:opacity-50">
                  {busy === run.runId ? <Loader2 className="h-3 w-3 animate-spin" /> : "Cancel"}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </Popover>
  );
}
