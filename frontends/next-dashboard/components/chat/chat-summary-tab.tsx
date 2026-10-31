"use client";

import { useCallback, useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { callTool } from "@/lib/api";
import { parseSession } from "@/lib/hooks/use-session-list";
import { loadSessionHistory } from "@/lib/hooks/use-session-history";
import { generateSessionSummary } from "@/components/operations/sessions/session-actions";

/**
 * Row 18 (feature-map) — the Summary tab, now in its PROPER upstream home
 * (chat right panel), reusing the same backend the Sessions-detail interim
 * surface uses: resolve the thread's session, show its rolling summary, and
 * regenerate on demand from the transcript excerpt (the session brick stays
 * free of transcript knowledge — the FE supplies the excerpt).
 */
export function ChatSummaryTab({ threadId }: { threadId: string }) {
  const [summary, setSummary] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const session = parseSession(await callTool("session_resolve_thread", { thread_id: threadId }));
      setSummary(session.summary);
      setError(null);
    } catch {
      setError("This chat isn’t saved as a session yet.");
    }
  }, [threadId]);

  useEffect(() => { void load(); }, [load]);

  const generate = async () => {
    setBusy(true); setError(null);
    try {
      const session = parseSession(await callTool("session_resolve_thread", { thread_id: threadId }));
      const messages = await loadSessionHistory(session.session_id);
      const excerpt = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => `${m.role}: ${typeof m.content === "string" ? m.content : ""}`)
        .join("\n").trim().slice(0, 24_000);
      if (!excerpt) { setError("No conversation to summarize yet."); return; }
      const updated = await generateSessionSummary(session.session_id, excerpt, session.revision);
      setSummary(updated.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn’t summarize this chat.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.15em] text-muted-foreground">
          <FileText className="h-3.5 w-3.5" /> Summary
        </span>
        <button type="button" disabled={busy} onClick={() => void generate()}
          className="rounded-lg border border-border/60 px-2.5 py-1 text-xs hover:bg-muted/50 disabled:opacity-50">
          {busy ? "Summarizing…" : summary ? "Regenerate" : "Generate"}
        </button>
      </div>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {summary
        ? <p className="whitespace-pre-wrap text-sm text-muted-foreground">{summary}</p>
        : <p className="text-sm italic text-muted-foreground/70">No summary yet — generate one to capture this conversation.</p>}
    </div>
  );
}
