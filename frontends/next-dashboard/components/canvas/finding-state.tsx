"use client";

import { useState } from "react";
import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { notifyFindingsChanged } from "@/lib/hooks/use-findings";
import { unwrapToolData } from "@/lib/tool-result-data";
import { cn } from "@/lib/utils";

/** The oracle's states, in the owner's words. */
export const STATE_LABELS: Readonly<Record<string, string>> = {
  candidate: "Open", verifying: "Verifying", verified: "Confirmed", refuted: "Dismissed",
};

export function FindingState({ findingId, state }: { findingId: string; state?: string }) {
  const [current, setCurrent] = useState(state ?? "candidate");
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const choose = async (next: string) => {
    if (next === current) return;
    setBusy(true); setNotice(null);
    try {
      unwrapToolData(await callTool("graph_set_finding_state", { finding_id: findingId, state: next }));
      setCurrent(next); notifyFindingsChanged();
    } catch (cause) { setNotice(withReason("Couldn’t change the state.", errorReason(cause))); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid gap-1">
      <div role="group" aria-label="Finding state" className="inline-flex w-fit overflow-hidden rounded-md border border-border/50">
        {Object.entries(STATE_LABELS).map(([value, label]) => (
          <button key={value} type="button" aria-pressed={current === value} disabled={busy} onClick={() => void choose(value)}
            className={cn("px-2 py-0.5 text-[10px] transition-colors", current === value ? "bg-accent/50 text-foreground" : "text-muted-foreground hover:bg-accent/30")}>
            {label}
          </button>
        ))}
      </div>
      {notice && <p role="alert" className="text-[11px] text-destructive">{notice}</p>}
    </div>
  );
}
