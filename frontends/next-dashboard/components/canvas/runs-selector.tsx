"use client";

import * as Popover from "@radix-ui/react-popover";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronDown, Circle, Loader2, RefreshCw, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface RunEntry {
  run_id: string;
  status: string;
  started_at: string;
}

interface RunsSelectorProps {
  listRecentRuns: (limit?: number) => Promise<RunEntry[]>;
  focusedRunId: string | null;
  onFocusRun: (runId: string) => void;
  onClear: () => void;
}

function StatusIcon({ status }: { status: string }) {
  if (["completed", "succeeded"].includes(status)) return <CheckCircle2 className="h-3 w-3 text-emerald-400" />;
  if (status === "failed") return <XCircle className="h-3 w-3 text-red-400" />;
  return <Circle className={cn("h-2.5 w-2.5 fill-current", status === "running" ? "text-sky-400" : "text-muted-foreground/50")} />;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function RunsSelector({ listRecentRuns, focusedRunId, onFocusRun, onClear }: RunsSelectorProps) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setRuns(await listRecentRuns(20)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Runs unavailable"); }
    finally { setLoading(false); }
  }, [listRecentRuns]);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label="Select a workflow run"
          className={cn(
            "inline-flex h-7 max-w-44 items-center gap-1.5 rounded-md border px-2 text-[10px] transition-colors",
            focusedRunId
              ? "border-sky-500/30 bg-sky-500/10 text-sky-200"
              : "border-border/40 text-muted-foreground hover:bg-accent/40 hover:text-foreground",
          )}
        >
          <Circle className={cn("h-2 w-2 fill-current", focusedRunId ? "text-sky-400" : "text-muted-foreground/40")} />
          <span className="truncate">{focusedRunId ? focusedRunId : "Runs / Workflows"}</span>
          <ChevronDown className="h-3 w-3 shrink-0" />
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          align="end"
          side="bottom"
          sideOffset={8}
          collisionPadding={16}
          className="z-50 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-border/50 bg-popover/95 shadow-xl backdrop-blur-md"
        >
          <div className="flex items-center gap-2 border-b border-border/30 px-3 py-2">
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Workflow runs</p>
              <p className="text-[10px] text-muted-foreground/60">Choose explicitly; activity never changes focus.</p>
            </div>
            <button type="button" onClick={() => void refresh()} disabled={loading} aria-label="Refresh workflow runs" className="rounded p-1 text-muted-foreground hover:bg-accent/40 hover:text-foreground">
              {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            </button>
          </div>
          {focusedRunId && (
            <button type="button" onClick={() => { onClear(); setOpen(false); }} className="w-full border-b border-border/20 px-3 py-2 text-left text-[11px] text-sky-300 hover:bg-accent/30">
              Clear focus · return to broad graph
            </button>
          )}
          <div className="max-h-64 overflow-y-auto p-1.5">
            {error && <p className="px-2 py-4 text-center text-[10px] text-red-400">Runs unavailable · {error}</p>}
            {!error && !loading && runs.length === 0 && <p className="px-2 py-4 text-center text-[10px] text-muted-foreground">No workflow runs are available.</p>}
            {runs.map((run) => (
              <button
                type="button"
                key={run.run_id}
                title={run.run_id}
                onClick={() => { onFocusRun(run.run_id); setOpen(false); }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors",
                  focusedRunId === run.run_id ? "bg-sky-500/10 text-sky-200" : "text-foreground/80 hover:bg-accent/30",
                )}
              >
                <StatusIcon status={run.status} />
                <span className="min-w-0 flex-1 truncate font-mono text-[11px]">{run.run_id}</span>
                <span className="text-[9px] text-muted-foreground">{formatTime(run.started_at)}</span>
              </button>
            ))}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
