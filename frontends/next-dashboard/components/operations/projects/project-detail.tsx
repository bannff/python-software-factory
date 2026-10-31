"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Pause, Play, Square } from "lucide-react";
import type { ActionResult } from "@/lib/hooks/use-projects";
import { fetchLoopCycle } from "@/lib/hooks/use-projects";
import type { Loop, LoopCycle } from "./project-types";
import { STATE_TONE } from "./project-card";

type Pending = "pause" | "resume" | "stop" | null;

/**
 * One project's (loop's) detail: objective, spec, latest settled cycle, and
 * the lifecycle controls the Workflow loop engine actually supports —
 * pause/resume/stop, each fenced by the record's revision.
 */
export function ProjectDetail({ loop, onClose, actions }: {
  loop: Loop;
  onClose: () => void;
  actions: {
    pause: (l: Loop) => Promise<ActionResult>;
    resume: (l: Loop) => Promise<ActionResult>;
    stop: (l: Loop) => Promise<ActionResult>;
  };
}) {
  const [pending, setPending] = useState<Pending>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [cycle, setCycle] = useState<LoopCycle | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let live = true;
    setCycle(null);
    void fetchLoopCycle(loop).then((c) => { if (live) setCycle(c); });
    return () => { live = false; };
  }, [loop]);

  const run = async (kind: Exclude<Pending, null>, fn: () => Promise<ActionResult>) => {
    setPending(kind); setNotice(null);
    const result = await fn();
    setPending(null);
    if (result.status === "conflict") setNotice("This project changed elsewhere — refreshed to the latest.");
    else if (result.status === "deleted") setNotice("This project no longer exists.");
    else if (result.status === "error") setNotice("That action didn't go through. Try again.");
  };

  return (
    <article className="rounded-xl border border-violet-500/30 bg-violet-500/[0.04] p-4">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 ref={headingRef} tabIndex={-1} className="truncate font-medium outline-none">{loop.objective}</h2>
          <p className="truncate text-xs text-muted-foreground">{loop.loopId}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${STATE_TONE[loop.state]}`}>{loop.state}</span>
          <button type="button" onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">Close</button>
        </div>
      </header>

      {notice && (
        <div role="status" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">{notice}</div>
      )}

      <dl className="mb-4 grid gap-2 text-sm sm:grid-cols-2">
        <Field label="Agent" value={loop.agentId} />
        <Field label="Interval" value={`${loop.intervalSeconds}s`} />
        <Field label="Cycle" value={`${loop.lastSettledCycle} / ${loop.maxCycles || "∞"}`} />
        <Field label="Terminal reason" value={loop.terminalReason ?? "—"} />
      </dl>

      <div className="mb-4 rounded-lg border border-border/40 bg-card/30 p-3">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground/60">Spec</p>
        <p className="mt-1 whitespace-pre-wrap break-words text-sm text-foreground/90">{loop.cycleInstructions}</p>
      </div>

      {cycle && (
        <div className="mb-4 rounded-lg border border-border/40 bg-card/30 p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground/60">Latest cycle ({cycle.cycle}) — {cycle.state}{cycle.disposition ? ` · ${cycle.disposition}` : ""}</p>
          {cycle.summary && <p className="mt-1 whitespace-pre-wrap break-words text-sm text-foreground/90">{cycle.summary}</p>}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {loop.state === "paused" ? (
          <ActionButton label="Resume" busy={pending === "resume"} disabled={pending !== null}
            onClick={() => run("resume", () => actions.resume(loop))} icon={Play} />
        ) : (
          <ActionButton label="Pause" busy={pending === "pause"} disabled={pending !== null || loop.state !== "active"}
            onClick={() => run("pause", () => actions.pause(loop))} icon={Pause} />
        )}
        <ActionButton label="Stop" busy={pending === "stop"} disabled={pending !== null || loop.state === "stopped" || loop.state === "completed"}
          tone="danger" onClick={() => run("stop", () => actions.stop(loop))} icon={Square} />
      </div>
    </article>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground/60">{label}</dt>
      <dd className="m-0 truncate text-sm text-foreground/90" title={value}>{value}</dd>
    </div>
  );
}

function ActionButton({ label, onClick, busy, disabled, icon: Icon, tone }: {
  label: string; onClick: () => void; busy: boolean; disabled: boolean;
  icon: typeof Play; tone?: "danger";
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={label}
      className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs transition-colors disabled:opacity-50 ${
        tone === "danger" ? "border-destructive/40 text-destructive hover:bg-destructive/10" : "border-border/60 hover:bg-muted/50"
      }`}>
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}
