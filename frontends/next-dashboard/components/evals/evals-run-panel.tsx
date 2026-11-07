"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Plus, X } from "lucide-react";
import { useMounted } from "@/lib/hooks/use-mounted";
import { listEvaluators, runExperiment, runFailure, type Evaluator, type RunOutcome } from "./evals-api";

const FIELD = "w-full rounded-md border bg-background/50 px-3 py-2 text-sm";
const BLANK_CASE = { input: "", expected: "" };

/** Start an evaluation run: a few cases, the evaluators to score them, and an optional name. */
export function EvalsRunPanel() {
  const [open, setOpen] = useState(false);
  const [cases, setCases] = useState([BLANK_CASE]);
  const [evaluators, setEvaluators] = useState<Evaluator[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [rubric, setRubric] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunOutcome | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useMounted();

  useEffect(() => {
    if (!open) return;
    void listEvaluators().then((e) => { if (mounted.current) setEvaluators(e); }).catch(() => undefined);
  }, [open, mounted]);

  const needsRubric = evaluators.some((e) => e.requiresRubric && chosen.includes(e.name));
  const setCase = (i: number, patch: Partial<typeof BLANK_CASE>) => setCases(cases.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const toggle = (n: string) => setChosen(chosen.includes(n) ? chosen.filter((x) => x !== n) : [...chosen, n]);

  const start = async () => {
    const filled = cases.filter((c) => c.input.trim());
    if (!filled.length) { setError("Enter at least one prompt to test."); return; }
    if (!chosen.length) { setError("Choose at least one evaluator."); return; }
    if (needsRubric && !rubric.trim()) { setError("Describe the rubric the chosen evaluator should score against."); return; }
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await runExperiment({
        cases: filled.map((c) => (c.expected.trim() ? { input: c.input.trim(), expected_output: c.expected.trim() } : { input: c.input.trim() })),
        evaluator_names: chosen, experiment_name: name.trim(), rubric: needsRubric ? rubric.trim() : "",
      });
      if (mounted.current) { setResult(r); setOpen(false); }
    } catch (cause) { if (mounted.current) setError(runFailure(cause)); }
    finally { if (mounted.current) setBusy(false); }
  };

  return (
    <section aria-label="Run an eval" className="grid gap-3 p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Run an eval</h3>
        {!open && <button type="button" aria-label="Run an eval" onClick={() => { setError(null); setOpen(true); }}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/60 px-2.5 py-1.5 text-xs hover:bg-accent/40">
          <FlaskConical className="h-3.5 w-3.5" aria-hidden /> Run an eval</button>}
      </div>
      {result && (
        <p role="status" className="text-xs text-emerald-400">
          Run finished · {result.cases} {result.cases === 1 ? "case" : "cases"}
          {result.overallScore !== null && ` · overall score ${result.overallScore.toFixed(2)}`}
          {result.passRate !== null && ` · pass rate ${Math.round(result.passRate * 100)}%`}
          {result.errors > 0 && ` · ${result.errors} could not be scored`}. Use the refresh icon to see it below.
        </p>
      )}
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {open && (
        <form onSubmit={(e) => { e.preventDefault(); void start(); }} className="grid gap-3 rounded-xl border border-border/60 bg-card/20 p-4">
          {cases.map((c, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <input aria-label={`Prompt ${i + 1}`} className={FIELD} placeholder="Prompt" value={c.input} onChange={(e) => setCase(i, { input: e.target.value })} />
              <input aria-label={`Expected answer ${i + 1}`} className={FIELD} placeholder="Expected answer (optional)" value={c.expected} onChange={(e) => setCase(i, { expected: e.target.value })} />
              {cases.length > 1 && <button type="button" aria-label={`Remove case ${i + 1}`} onClick={() => setCases(cases.filter((_, j) => j !== i))} className="rounded-md border px-2"><X className="h-3.5 w-3.5" aria-hidden /></button>}
            </div>
          ))}
          <button type="button" aria-label="Add case" onClick={() => setCases([...cases, BLANK_CASE])} className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <Plus className="h-3.5 w-3.5" aria-hidden /> Add case</button>
          <fieldset className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
            <legend className="mb-1.5">Evaluators</legend>
            {evaluators.map((e) => (
              <label key={e.name} title={e.description} className="inline-flex items-center gap-1.5">
                <input type="checkbox" aria-label={e.name} checked={chosen.includes(e.name)} onChange={() => toggle(e.name)} /> {e.name}</label>
            ))}
          </fieldset>
          {needsRubric && <label className="grid gap-1 text-xs"><span>Rubric</span>
            <textarea aria-label="Rubric" className={FIELD} rows={2} value={rubric} onChange={(e) => setRubric(e.target.value)} /></label>}
          <label className="grid gap-1 text-xs"><span>Run name</span>
            <input aria-label="Run name" className={FIELD} value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional" /></label>
          <div className="flex gap-2">
            <button type="submit" disabled={busy} className="rounded-md bg-violet-500 px-3 py-2 text-xs text-white disabled:opacity-40">{busy ? "Running…" : "Start run"}</button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-md border px-3 py-2 text-xs">Cancel</button>
          </div>
        </form>
      )}
    </section>
  );
}
