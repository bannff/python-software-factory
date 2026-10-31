"use client";

import { useState } from "react";
import { CheckCheck, Loader2, MessageSquare, Quote, Send, X } from "lucide-react";
import type { ArtifactComment } from "./artifact-types";
import { markArtifactCommentReview, postArtifactComment } from "./artifact-actions";

function AnchorSnippet({ text, orphaned }: { text: string; orphaned: boolean }) {
  return (
    <div className={`mb-1.5 flex items-start gap-1.5 rounded-md border-l-2 px-2 py-1 text-[11px] ${
      orphaned ? "border-amber-500/50 bg-amber-500/5 text-amber-300" : "border-violet-500/50 bg-violet-500/5 text-violet-300"
    }`}>
      <Quote className="mt-0.5 h-3 w-3 shrink-0" />
      <span className="line-clamp-2 italic">
        {orphaned ? "Selected text no longer found in the artifact — " : ""}&ldquo;{text}&rdquo;
      </span>
    </div>
  );
}

export function ArtifactComments({
  slug, comments, loading, onChanged, artifactContent, pendingAnchor, onClearAnchor,
}: {
  slug: string;
  comments: ArtifactComment[];
  loading: boolean;
  onChanged: () => void;
  /** Current artifact body text, used to detect an anchor whose quoted span
   * no longer exists (edited or reverted away) instead of guessing. */
  artifactContent?: string;
  /** A text selection captured from the preview, staged to attach to the
   * next comment posted. */
  pendingAnchor?: string | null;
  onClearAnchor?: () => void;
}) {
  const [body, setBody] = useState("");
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const post = async () => {
    if (!body.trim()) return;
    setWorking("post"); setError(null);
    try {
      await postArtifactComment(slug, body, pendingAnchor);
      setBody(""); onClearAnchor?.(); onChanged();
    }
    catch { setError("Comment could not be posted. Refresh the artifact and try again."); }
    finally { setWorking(null); }
  };
  const review = async (id: string) => {
    setWorking(id); setError(null);
    try { await markArtifactCommentReview(slug, id); onChanged(); }
    catch { setError("Comment status changed elsewhere. Refresh and try again."); }
    finally { setWorking(null); }
  };
  return (
    <section aria-labelledby="artifact-comments-title" className="space-y-3">
      <div className="flex items-center gap-2"><MessageSquare className="h-4 w-4 text-violet-400" /><h3 id="artifact-comments-title" className="text-sm font-medium">Comments</h3></div>
      {pendingAnchor && (
        <div role="status" className="flex items-start gap-1.5 rounded-md border border-violet-500/40 bg-violet-500/10 px-2 py-1.5 text-[11px] text-violet-200">
          <Quote className="mt-0.5 h-3 w-3 shrink-0" />
          <span className="line-clamp-2 flex-1 italic">Commenting on: &ldquo;{pendingAnchor}&rdquo;</span>
          <button type="button" aria-label="Clear selected text" onClick={onClearAnchor} className="shrink-0 text-violet-300 hover:text-violet-100"><X className="h-3 w-3" /></button>
        </div>
      )}
      <div className="flex gap-2"><input aria-label="New artifact comment" value={body} onChange={(event) => setBody(event.target.value)} placeholder={pendingAnchor ? "Comment on the selected text…" : "Leave feedback…"} className="min-w-0 flex-1 rounded-lg border border-border/60 bg-background/60 px-3 py-2 text-xs outline-none focus:border-violet-500/50" /><button type="button" aria-label="Post comment" onClick={post} disabled={!body.trim() || working !== null} className="rounded-lg bg-violet-500/15 p-2 text-violet-300 disabled:opacity-40">{working === "post" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</button></div>
      {error && <div role="alert" className="text-xs text-amber-300">{error}</div>}
      {loading && comments.length === 0 ? <p className="text-xs text-muted-foreground">Loading comments…</p> : comments.length === 0 ? <p className="text-xs text-muted-foreground">No comments yet.</p> : <ul className="space-y-2">{comments.map((comment) => <li key={comment.id} className={`rounded-lg border border-border/50 bg-muted/10 p-3 ${comment.parent_id ? "ml-5" : ""}`}>{comment.anchor_text && <AnchorSnippet text={comment.anchor_text} orphaned={artifactContent !== undefined && !artifactContent.includes(comment.anchor_text)} />}<div className="flex items-center justify-between gap-2"><p className="text-[11px] text-muted-foreground">{comment.actor_kind} · {comment.status}</p>{!comment.parent_id && comment.status === "open" && <button type="button" onClick={() => review(comment.id)} disabled={working !== null} className="inline-flex items-center gap-1 text-[11px] text-violet-300 disabled:opacity-40"><CheckCheck className="h-3 w-3" /> Mark review</button>}</div><p className="mt-1 whitespace-pre-wrap text-xs text-foreground/85">{comment.body}</p></li>)}</ul>}
    </section>
  );
}
