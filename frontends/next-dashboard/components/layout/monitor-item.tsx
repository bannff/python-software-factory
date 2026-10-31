"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Play, Radar, Square } from "lucide-react";
import { useAgent } from "@copilotkit/react-core/v2";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import { Popover } from "@/components/ui/popover";

const AGENT_ID = "companion_x";
const DEFAULT_INTERVAL = 300;
const DEFAULT_MAX_CYCLES = 24;
const POLL_MS = 10_000;
const MAX_CONSECUTIVE_FAILURES = 3;
const ACTIVE = new Set(["active"]);

interface MonitorLoop {
  loopId: string; objective: string; state: string; revision: number;
}

function parseLoops(raw: unknown, threadId: string): MonitorLoop[] {
  const data = unwrapToolData(raw) as Record<string, unknown>;
  const rows = Array.isArray(data.loops) ? data.loops : [];
  return rows.filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null)
    .filter((r) => r.kind === "monitor" && r.origin_thread_id === threadId
      && r.state !== "stopped" && r.state !== "completed")
    .map((r) => ({
      loopId: String(r.loop_id ?? ""), objective: String(r.objective ?? ""),
      state: String(r.state ?? ""), revision: Number(r.revision ?? 0),
    }))
    .filter((r) => r.loopId);
}

/**
 * Row 58 (Monitor loops) — arm/view/stop a same-session bounded monitor from
 * the composer chrome. Backed entirely by the existing durable Workflow loop
 * engine (``workflow.start_loop`` kind="monitor" / ``list_loops`` /
 * ``stop_loop``) — the same M7.6 engine used for Task Runner (row 77) and
 * Schedules (row 55). ``list_loops`` scopes by tenant/owner only, so the
 * thread filter here is load-bearing, not cosmetic (consult meta `afe02757`).
 */
export function MonitorItem() {
  const { agent } = useAgent({ agentId: AGENT_ID });
  const threadId = agent?.threadId ?? "";
  const [loops, setLoops] = useState<MonitorLoop[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [arming, setArming] = useState(false);
  const [objective, setObjective] = useState("");
  const [instructions, setInstructions] = useState("");
  const failureCount = useRef(0);

  const refresh = useCallback(async () => {
    if (!threadId) return;
    try {
      setLoops(parseLoops(await callTool("workflow.list_loops", {}), threadId));
      setError(null);
      setUnavailable(false);
      failureCount.current = 0;
    } catch {
      setError("Monitor status unavailable");
      failureCount.current += 1;
      if (failureCount.current >= MAX_CONSECUTIVE_FAILURES) setUnavailable(true);
    }
  }, [threadId]);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => { if (!unavailable) void refresh(); }, POLL_MS);
    return () => clearInterval(id);
  }, [refresh, unavailable]);

  const arm = async () => {
    if (!threadId || !objective.trim() || !instructions.trim()) return;
    setBusy("arm");
    try {
      unwrapToolData(await callTool("workflow.start_loop", {
        kind: "monitor", agent_id: AGENT_ID, objective, cycle_instructions: instructions,
        interval_seconds: DEFAULT_INTERVAL, max_cycles: DEFAULT_MAX_CYCLES,
      }));
      setObjective(""); setInstructions(""); setArming(false);
    } finally { setBusy(null); await refresh(); }
  };

  const stop = async (loop: MonitorLoop) => {
    setBusy(loop.loopId);
    try { unwrapToolData(await callTool("workflow.stop_loop", { loop_id: loop.loopId, expected_revision: loop.revision })); }
    finally { setBusy(null); await refresh(); }
  };

  const activeCount = loops.filter((l) => ACTIVE.has(l.state)).length;

  return (
    <Popover align="right" trigger={
      <div className="flex items-center gap-1 text-muted-foreground" aria-label="Monitors">
        <Radar className="h-3 w-3" /><span>{activeCount}</span>
      </div>
    }>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-medium text-foreground">Monitors (this session)</span>
          {!arming && <button type="button" onClick={() => setArming(true)} className="flex items-center gap-1 text-violet-400 hover:underline">
            <Play className="h-3 w-3" /> Arm
          </button>}
        </div>
        {unavailable && <p className="text-muted-foreground">Monitors unavailable right now.</p>}
        {!unavailable && error && <p className="text-destructive">{error}</p>}
        {!unavailable && !error && !arming && loops.length === 0 && <p className="text-muted-foreground">No monitors running.</p>}

        {arming && (
          <div className="space-y-1.5">
            <input value={objective} onChange={(e) => setObjective(e.target.value)} placeholder="What to watch"
              className="w-full rounded-md border border-border/50 bg-background/50 px-2 py-1 text-xs" />
            <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={2}
              placeholder="What to check each cycle"
              className="w-full rounded-md border border-border/50 bg-background/50 px-2 py-1 text-xs" />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setArming(false)} className="text-muted-foreground hover:underline">Cancel</button>
              <button type="button" onClick={() => void arm()} disabled={busy === "arm" || !objective.trim() || !instructions.trim()}
                className="flex items-center gap-1 text-violet-400 disabled:opacity-50">
                {busy === "arm" ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Start
              </button>
            </div>
          </div>
        )}

        <div className="max-h-[180px] space-y-1 overflow-y-auto">
          {loops.map((loop) => (
            <div key={loop.loopId} className="flex items-center gap-2 rounded px-1.5 py-1 hover:bg-accent/30">
              <span className="min-w-0 flex-1 truncate text-foreground" title={loop.objective}>{loop.objective}</span>
              <span className="shrink-0 text-muted-foreground">{loop.state}</span>
              {ACTIVE.has(loop.state) && (
                <button type="button" onClick={() => void stop(loop)} disabled={busy === loop.loopId}
                  aria-label={`Stop ${loop.loopId}`} className="shrink-0 text-destructive hover:underline disabled:opacity-50">
                  {busy === loop.loopId ? <Loader2 className="h-3 w-3 animate-spin" /> : <Square className="h-3 w-3" />}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </Popover>
  );
}
