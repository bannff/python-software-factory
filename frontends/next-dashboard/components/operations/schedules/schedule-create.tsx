"use client";

import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
import type { ActionResult } from "@/lib/hooks/use-schedules";
import { isCreateInputComplete, type ScheduleCreateInput, type ScheduleKind } from "./schedule-types";

const DEFAULT_AGENT = "companion-x-default";

/**
 * Row 55 (Schedule) creation control. Agent-turn schedules only — the
 * scheduler's ``kind`` is the timing axis (interval/one_shot/cron); every
 * fire dispatches an LLM turn today, so this form is honest end-to-end with
 * zero backend change. Script/command execution kinds are a separate,
 * explicitly deferred slice (consult meta `dab287c6`).
 */
export function ScheduleCreateDialog({ onClose, onCreate }: {
  onClose: () => void;
  onCreate: (input: ScheduleCreateInput) => Promise<ActionResult>;
}) {
  const [agentId, setAgentId] = useState(DEFAULT_AGENT);
  const [task, setTask] = useState("");
  const [kind, setKind] = useState<ScheduleKind>("interval");
  const [intervalSeconds, setIntervalSeconds] = useState(3600);
  const [oneShotAt, setOneShotAt] = useState("");
  const [cronExpression, setCronExpression] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const input: ScheduleCreateInput = {
    agentId, task, kind,
    intervalSeconds: kind === "interval" ? intervalSeconds : undefined,
    oneShotAt: kind === "one_shot" && oneShotAt ? new Date(oneShotAt).toISOString() : undefined,
    cronExpression: kind === "cron" ? cronExpression : undefined,
  };
  const canCreate = isCreateInputComplete(input) && !busy;

  const submit = async () => {
    setBusy(true); setError(null);
    const result = await onCreate(input);
    setBusy(false);
    if (result.status === "ok") onClose();
    else setError("That schedule didn't go through. Check the fields and try again.");
  };

  return (
    <div role="dialog" aria-labelledby="schedule-create-title" className="rounded-xl border border-violet-500/30 bg-card/95 p-4">
      <header className="mb-3 flex items-center justify-between">
        <h2 id="schedule-create-title" className="text-sm font-medium">New schedule</h2>
        <button type="button" onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </header>

      {error && <p role="alert" className="mb-3 rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs">{error}</p>}

      <label className="block text-xs font-medium text-muted-foreground" htmlFor="sc-agent">Agent</label>
      <input id="sc-agent" value={agentId} onChange={(e) => setAgentId(e.target.value)}
        className="mt-1 w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm" />

      <label className="mt-3 block text-xs font-medium text-muted-foreground" htmlFor="sc-task">Task</label>
      <textarea id="sc-task" value={task} onChange={(e) => setTask(e.target.value)} rows={3}
        placeholder="What should this run do each time it fires?"
        className="mt-1 w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm" />

      <fieldset className="mt-3">
        <legend className="text-xs font-medium text-muted-foreground">Timing</legend>
        <div role="radiogroup" aria-label="Timing kind" className="mt-1 flex gap-1.5">
          {(["interval", "one_shot", "cron"] as const).map((k) => (
            <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)}
              className={`rounded-md border px-2.5 py-1 text-xs ${kind === k ? "border-violet-500/50 bg-violet-500/10 text-violet-300" : "border-border/60 text-muted-foreground hover:bg-muted/30"}`}>
              {k === "interval" ? "Every N seconds" : k === "one_shot" ? "Once at a time" : "Cron expression"}
            </button>
          ))}
        </div>
      </fieldset>

      {kind === "interval" && (
        <div className="mt-2">
          <label className="block text-[11px] text-muted-foreground" htmlFor="sc-interval">Interval (seconds)</label>
          <input id="sc-interval" type="number" min={15} max={86400} value={intervalSeconds}
            onChange={(e) => setIntervalSeconds(Number(e.target.value) || 3600)}
            className="mt-1 w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm" />
        </div>
      )}
      {kind === "one_shot" && (
        <div className="mt-2">
          <label className="block text-[11px] text-muted-foreground" htmlFor="sc-when">Fire at</label>
          <input id="sc-when" type="datetime-local" value={oneShotAt} onChange={(e) => setOneShotAt(e.target.value)}
            className="mt-1 w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm" />
        </div>
      )}
      {kind === "cron" && (
        <div className="mt-2">
          <label className="block text-[11px] text-muted-foreground" htmlFor="sc-cron">Cron expression</label>
          <input id="sc-cron" value={cronExpression} onChange={(e) => setCronExpression(e.target.value)}
            placeholder="0 9 * * 1"
            className="mt-1 w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm font-mono" />
        </div>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Cancel</button>
        <button type="button" onClick={() => void submit()} disabled={!canCreate}
          className="flex items-center gap-1.5 rounded-md bg-violet-500 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />} Create schedule
        </button>
      </div>
    </div>
  );
}
