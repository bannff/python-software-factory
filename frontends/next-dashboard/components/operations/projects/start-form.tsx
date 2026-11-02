"use client";

import { useState } from "react";
import { Loader2, Play } from "lucide-react";
import { withReason } from "@/lib/error-reason";
import { usePersonas } from "@/lib/hooks/use-personas";
import { useSessionList } from "@/lib/hooks/use-session-list";
import type { ActionResult, StartLoopSpec } from "@/lib/hooks/use-projects";

const DEFAULT_AGENT = "companion-x-default";
const CONTROL = "w-full rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm";

export function StartForm({ onStart }: { onStart: (input: StartLoopSpec) => Promise<ActionResult> }) {
  const { personas } = usePersonas();
  const { sessions } = useSessionList(false);
  const [title, setTitle] = useState("");
  const [spec, setSpec] = useState("");
  const [agentChoice, setAgentChoice] = useState<string | null>(null);
  const [sessionChoice, setSessionChoice] = useState<string | null>(null);
  const [interval, setInterval_] = useState(300);
  const [maxCycles, setMaxCycles] = useState(24);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const agentId = agentChoice ?? (personas.find((p) => p.id === DEFAULT_AGENT) ?? personas[0])?.id ?? "";
  const originThreadId = sessionChoice ?? sessions[0]?.thread_id ?? "";
  const canStart = title.trim() !== "" && spec.trim() !== "" && agentId !== "" && originThreadId !== "" && !busy;

  const submit = async () => {
    setBusy(true);
    setFailure(null);
    const result = await onStart({
      title, spec, agentId, originThreadId, intervalSeconds: interval, maxCycles,
    });
    setBusy(false);
    if (result.status === "ok") { setTitle(""); setSpec(""); return; }
    setFailure(withReason("Could not start the project", result.reason));
  };

  return (
    <form className="rounded-xl border border-border/50 bg-card/30 p-4"
      onSubmit={(e) => { e.preventDefault(); if (canStart) void submit(); }}>
      <label className="block text-xs font-medium text-muted-foreground" htmlFor="project-title">Title</label>
      <input id="project-title" value={title} onChange={(e) => setTitle(e.target.value)}
        placeholder="What is this project trying to achieve?"
        className="mt-1 w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm" />
      <label className="mt-3 block text-xs font-medium text-muted-foreground" htmlFor="project-spec">Spec</label>
      <textarea id="project-spec" value={spec} onChange={(e) => setSpec(e.target.value)} rows={4}
        placeholder="Describe the multi-step work each cycle should advance."
        className="mt-1 w-full rounded-md border border-border/60 bg-background px-3 py-2 text-sm" />
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Agent" htmlFor="project-agent">
          <select id="project-agent" value={agentId} onChange={(e) => setAgentChoice(e.target.value)} className={CONTROL}>
            {personas.map((p) => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
          </select>
        </Field>
        <Field label="Session" htmlFor="project-session">
          <select id="project-session" value={originThreadId} onChange={(e) => setSessionChoice(e.target.value)} className={CONTROL}>
            {sessions.map((s) => <option key={s.thread_id} value={s.thread_id}>{s.title || s.session_id}</option>)}
          </select>
        </Field>
        <Field label="Interval (seconds)" htmlFor="project-interval">
          <input id="project-interval" type="number" min={15} max={86400} value={interval}
            onChange={(e) => setInterval_(Number(e.target.value) || 300)} className={CONTROL} />
        </Field>
        <Field label="Max cycles" htmlFor="project-max-cycles">
          <input id="project-max-cycles" type="number" min={0} max={10000} value={maxCycles}
            onChange={(e) => setMaxCycles(Number(e.target.value) || 24)} className={CONTROL} />
        </Field>
      </div>
      {failure && <p role="alert" className="mt-3 text-sm text-destructive">{failure}</p>}
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
