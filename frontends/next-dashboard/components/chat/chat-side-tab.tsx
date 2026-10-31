"use client";

import { useEffect, useState } from "react";
import { MessagesSquare } from "lucide-react";
import { parseSideCommand } from "@/lib/chat/side-chat";

interface ScratchEntry { id: string; query: string }

/**
 * Row 19 (feature-map) — the Side tab: a scratch sub-conversation beside the
 * main turn. This slice ships the surface + entry-point seam (its own input,
 * `/side`·`/btw` command parsing, and an optional `seed` from "Ask about
 * this"). Each submitted line is recorded in a local scratch transcript.
 *
 * Honest scaffold (owner ruling 16:20): running the side turn — read-only
 * lookups (file reads, searches, fetches, read-only shell) executed WITHOUT
 * approval, changes REFUSED — is the deferred backend half (`handlers/side.py`
 * + a read-only tool-approval policy). Until that lands the tab collects the
 * scratch conversation and discloses that answers are pending, rather than
 * faking an assistant reply.
 */
export function ChatSideTab({ seed }: { seed?: string }) {
  const [draft, setDraft] = useState("");
  const [entries, setEntries] = useState<ScratchEntry[]>([]);

  useEffect(() => { if (seed) setDraft(seed); }, [seed]);

  const submit = () => {
    const { query } = parseSideCommand(draft);
    const text = query.trim();
    if (!text) return;
    setEntries((prev) => [{ id: `${Date.now()}-${prev.length}`, query: text }, ...prev]);
    setDraft("");
  };

  return (
    <div className="flex h-full flex-col gap-3" aria-label="Side chat">
      <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.15em] text-muted-foreground">
        <MessagesSquare className="h-3.5 w-3.5" /> Side
      </span>
      <p className="text-xs text-muted-foreground/80">
        A scratch sub-conversation beside the main turn. Read-only lookups run here without
        interrupting the main chat; changes are refused.
      </p>
      <div className="flex gap-1.5">
        <input value={draft} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }}
          placeholder="Ask on the side… (/side or /btw)" aria-label="Side chat input"
          className="min-w-0 flex-1 rounded-md border border-border/60 bg-background/60 px-2.5 py-1 text-xs" />
        <button type="button" onClick={submit}
          className="shrink-0 rounded-md border border-border/60 px-2.5 py-1 text-xs hover:bg-muted/50">Ask</button>
      </div>
      {entries.length === 0 ? (
        <p className="text-sm italic text-muted-foreground/70">No side questions yet.</p>
      ) : (
        <ul className="flex min-h-0 flex-1 flex-col gap-2 overflow-auto">
          {entries.map((entry) => (
            <li key={entry.id} className="rounded-md border border-border/40 p-2">
              <p className="text-sm">{entry.query}</p>
              <p className="mt-1 text-[11px] italic text-muted-foreground/60">
                Answer pending — side-turn execution (read-only tools) not wired yet.
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
