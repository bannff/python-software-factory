"use client";

import { useCallback, useEffect, useState } from "react";
import { Pin, X } from "lucide-react";
import { callTool } from "@/lib/api";
import { parseSession } from "@/lib/hooks/use-session-list";
import { loadSessionHistory } from "@/lib/hooks/use-session-history";
import { togglePinnedMessage } from "@/lib/copilotkit/chat-pin";

/**
 * Row 9 (feature-map) — the "pins panel per session", now homed in the chat
 * side panel (the surface it was blocked on). Resolves the thread's session,
 * maps its ``pinned_message_ids`` to the real transcript messages, and lists
 * them with unpin. Backend (`session_set_pinned_messages`) + the message
 * toolbar pin toggle already shipped; this closes the viewing half.
 */
interface PinnedItem { id: string; role: string; text: string }

export function ChatPinsTab({ threadId }: { threadId: string }) {
  const [items, setItems] = useState<PinnedItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const session = parseSession(await callTool("session_resolve_thread", { thread_id: threadId }));
      const pinned = new Set(session.pinned_message_ids);
      if (pinned.size === 0) { setItems([]); setError(null); return; }
      const messages = await loadSessionHistory(session.session_id);
      setItems(messages
        .filter((m) => pinned.has(m.id))
        .map((m) => ({ id: m.id, role: m.role, text: typeof m.content === "string" ? m.content : "" })));
      setError(null);
    } catch {
      setError("This chat isn’t saved as a session yet.");
    }
  }, [threadId]);

  useEffect(() => { void load(); }, [load]);

  const unpin = async (messageId: string) => {
    setBusy(true);
    try { await togglePinnedMessage(threadId, messageId); await load(); }
    catch { setError("Couldn’t unpin that message."); }
    finally { setBusy(false); }
  };

  return (
    <div className="flex flex-col gap-3">
      <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.15em] text-muted-foreground">
        <Pin className="h-3.5 w-3.5" /> Pinned messages
      </span>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      {items && items.length === 0 && !error && (
        <p className="text-sm italic text-muted-foreground/70">No pinned messages — pin one from a reply’s ⋯ toolbar.</p>
      )}
      {items?.map((item) => (
        <div key={item.id} className="flex items-start gap-2 rounded-md border border-border/50 bg-card/20 p-2">
          <span className="min-w-0 flex-1">
            <span className="text-[10px] uppercase tracking-wide text-violet-400">{item.role}</span>
            <span className="mt-0.5 block truncate text-xs text-muted-foreground" title={item.text}>{item.text || "—"}</span>
          </span>
          <button type="button" aria-label={`Unpin ${item.id}`} disabled={busy} onClick={() => void unpin(item.id)}
            className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-accent/40 hover:text-foreground disabled:opacity-50">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
