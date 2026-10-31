"use client";

import { useState } from "react";
import { ListTodo, Loader2, Play, RefreshCw } from "lucide-react";
import { useProjects } from "@/lib/hooks/use-projects";
import { ProjectCard } from "./project-card";
import { ProjectDetail } from "./project-detail";
import type { Loop } from "./project-types";

const DEFAULT_AGENT = "companion-x-default";

/**
 * Task Runner (feature-map rows 77-78, Agent Capabilities → Projects).
 * A spec form starts an autonomous multi-step run on the existing durable
 * Workflow loop engine (``workflow.start_loop`` — the same engine driving
 * Companion-X's own goal loop). No new backend: title/spec map onto the
 * loop's ``objective``/``cycle_instructions``. List + detail + pause/resume/
 * stop round-trip through the real MCP tools; no fabricated states.
 */
export default function ProjectsView() {
  const { loops, loading, error, refresh, start, pause, resume, stop } = useProjects();
  const [selected, setSelected] = useState<string | null>(null);
  const [gone, setGone] = useState(false);

  const active: Loop | null = loops.find((l) => l.loopId === selected) ?? null;

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="projects-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Agent Capabilities</p>
          <h1 id="projects-title" className="mt-1 text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="mt-1 text-sm text-muted-foreground">Autonomous multi-step runs from a spec, driven by Companion X's own loop engine.</p>
        </div>
        <button type="button" onClick={refresh} aria-label="Refresh projects"
          className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      <StartForm onStart={async (input) => {
        const result = await start(input);
        if (result.status !== "ok") setGone(false);
      }} />

      {gone && (
        <div role="status" className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
          That project no longer exists.
          <button type="button" onClick={() => setGone(false)} className="ml-2 underline hover:no-underline">Dismiss</button>
        </div>
      )}

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Projects unavailable: {error}</span>
          <button type="button" onClick={refresh} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && loops.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading projects…
        </div>
      )}

      {!loading && !error && loops.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border/60 p-10 text-center">
          <ListTodo className="h-8 w-8 text-violet-400/70" />
          <h2 className="mt-3 font-medium">No projects yet</h2>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">Give it a spec above and it will run cycle by cycle until done.</p>
        </div>
      )}

      {!error && loops.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(320px,1.35fr)]">
          <ul className="grid content-start gap-3" aria-label="Projects">
            {loops.map((loop) => (
              <li key={loop.loopId}>
                <ProjectCard loop={loop} selected={loop.loopId === selected}
                  onOpen={() => { setSelected(loop.loopId); setGone(false); }} />
              </li>
            ))}
          </ul>
          {active ? (
            <ProjectDetail key={active.loopId} loop={active} onClose={() => setSelected(null)}
              actions={{ pause, resume, stop }} />
          ) : (
            <div className="hidden items-center justify-center rounded-xl border border-dashed border-border/50 p-8 text-center text-sm text-muted-foreground lg:flex">
              Select a project to see its cycles and controls.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function StartForm({ onStart }: { onStart: (input: {
  title: string; spec: string; agentId: string; intervalSeconds: number; maxCycles: number;
}) => Promise<void> }) {
  const [title, setTitle] = useState("");
  const [spec, setSpec] = useState("");
  const [agentId, setAgentId] = useState(DEFAULT_AGENT);
  const [interval, setInterval_] = useState(300);
  const [maxCycles, setMaxCycles] = useState(24);
  const [busy, setBusy] = useState(false);
  const canStart = title.trim().length > 0 && spec.trim().length > 0 && !busy;

  return (
    <form className="rounded-xl border border-border/50 bg-card/30 p-4" onSubmit={async (e) => {
      e.preventDefault();
      if (!canStart) return;
      setBusy(true);
      await onStart({ title, spec, agentId, intervalSeconds: interval, maxCycles });
      setBusy(false);
      setTitle(""); setSpec("");
    }}>
      <label className="block text-xs font-medium text-muted-foreground" htmlFor="project-title">Title</label>
      <input id="project-title" value={title} onChange={(e) => setTitle(e.target.value)}
        placeholder="What is this project trying to achieve?"
        className="mt-1 w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm" />
      <label className="mt-3 block text-xs font-medium text-muted-foreground" htmlFor="project-spec">Spec</label>
      <textarea id="project-spec" value={spec} onChange={(e) => setSpec(e.target.value)} rows={4}
        placeholder="Describe the multi-step work each cycle should advance."
        className="mt-1 w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm" />
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <Field label="Agent" htmlFor="project-agent">
          <input id="project-agent" value={agentId} onChange={(e) => setAgentId(e.target.value)}
            className="w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm" />
        </Field>
        <Field label="Interval (seconds)" htmlFor="project-interval">
          <input id="project-interval" type="number" min={15} max={86400} value={interval}
            onChange={(e) => setInterval_(Number(e.target.value) || 300)}
            className="w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm" />
        </Field>
        <Field label="Max cycles" htmlFor="project-max-cycles">
          <input id="project-max-cycles" type="number" min={0} max={10000} value={maxCycles}
            onChange={(e) => setMaxCycles(Number(e.target.value) || 24)}
            className="w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm" />
        </Field>
      </div>
      <button type="submit" disabled={!canStart}
        className="mt-3 flex items-center gap-1.5 rounded-md bg-violet-500 px-3 py-2 text-xs font-medium text-white disabled:opacity-50">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />} Start project
      </button>
    </form>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: React.ReactNode }) {
  return <div><label className="block text-[11px] text-muted-foreground" htmlFor={htmlFor}>{label}</label><div className="mt-1">{children}</div></div>;
}
