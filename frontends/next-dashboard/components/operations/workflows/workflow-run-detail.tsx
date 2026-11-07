"use client";

import { useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { parseRunDetail, type WorkflowRunDetail } from "./workflow-library-types";

function Json({ label, value }: { label: string; value: Record<string, unknown> }) {
  return <div><dt className="text-muted-foreground">{label}</dt>
    <dd><pre className="mt-1 max-h-48 overflow-auto rounded-md bg-muted/40 p-2 font-mono">{JSON.stringify(value, null, 2)}</pre></dd></div>;
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return <div><dt className="text-muted-foreground">{label}</dt><dd className={mono ? "font-mono" : undefined}>{value}</dd></div>;
}

/** One run read fresh from ``workflow.get_run``; the list row may be a poll behind. */
export function WorkflowRunDetailPanel({ runId }: { runId: string }) {
  const [detail, setDetail] = useState<WorkflowRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    callTool("workflow_get_run", { run_id: runId }).then((raw) => {
      if (!live) return;
      const parsed = parseRunDetail(raw);
      if (parsed) setDetail(parsed); else setError("Couldn't load this run.");
    }).catch((cause) => {
      if (live) setError(withReason("Couldn't load this run.", errorReason(cause)));
    });
    return () => { live = false; };
  }, [runId]);

  return <section aria-label={`Run ${runId} details`} className="mt-2 rounded-md border border-border/40 bg-background/40 p-3">
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {!error && !detail && <p className="text-muted-foreground">Loading run…</p>}
    {detail && <dl className="grid gap-2">
      <Row label="Status" value={detail.status} />
      {detail.currentStepId && <Row label="Current step" value={detail.currentStepId} mono />}
      {detail.waitingForEventType && <Row label="Waiting for event" value={detail.waitingForEventType} mono />}
      <Row label="Started" value={detail.startedAt} />
      <Row label="Updated" value={detail.updatedAt} />
      {detail.error && <Row label="Error" value={detail.error} />}
      {Object.keys(detail.input).length > 0 && <Json label="Input" value={detail.input} />}
      {detail.result && <Json label="Result" value={detail.result} />}
    </dl>}
  </section>;
}
