"use client";

import { useEffect, useMemo, useState } from "react";
import { useToolData } from "@companion-x/shared-renderer";
import type { JsonSerializable } from "@copilotkit/react-core/v2";
import { useAgentContext } from "@copilotkit/react-core/v2";
import type { Artifact, ArtifactComment, ArtifactVersion } from "./artifact-types";
import { rows } from "./artifact-types";
import { ArtifactPreview } from "./artifact-preview";
import { ArtifactEditor } from "./artifact-editor";
import { ArtifactHistory } from "./artifact-history";
import { ArtifactComments } from "./artifact-comments";
import {
  ARTIFACT_EVENT_UNAVAILABLE_MESSAGE, ARTIFACT_PURGE_FAILED_MESSAGE,
  artifactFailureMessage, deleteArtifact, purgeArtifact, revertArtifact,
  STALE_ARTIFACT_MESSAGE,
} from "./artifact-actions";

/** Content over this length is summarized, not sent whole, into the agent
 * prompt context — keeps a large document/widget artifact from ballooning
 * every chat turn's token budget while still letting the agent "see" it. */
const CONTEXT_CONTENT_CAP = 4_000;

export function ArtifactDetail({
  artifact, onClose, onChanged, onDeleted, tombstoned = false,
}: {
  artifact: Artifact; onClose: () => void; onChanged: () => void;
  onDeleted?: (tombstone: Artifact) => void; tombstoned?: boolean;
}) {
  const [current, setCurrent] = useState(artifact);
  const [reverting, setReverting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmingPurge, setConfirmingPurge] = useState(false);
  const [purging, setPurging] = useState(false);
  const [purged, setPurged] = useState(false);
  const [pendingAnchor, setPendingAnchor] = useState<string | null>(null);
  useEffect(() => { if (artifact.revision >= current.revision) setCurrent(artifact); }, [artifact, current.revision]);
  // A tombstoned artifact is gone from the reads; skip re-fetching its
  // versions/comments rather than generating failing tool calls.
  const versions = useToolData(tombstoned ? undefined : "artifacts_versions", { slug: current.slug });
  const comments = useToolData(tombstoned ? undefined : "artifacts_get_comments", { slug: current.slug });
  const versionRows = rows<ArtifactVersion>(versions.data, "versions");
  const commentRows = rows<ArtifactComment>(comments.data, "comments");
  const changed = (next: Artifact) => {
    setCurrent(next); onChanged(); versions.refetch();
  };
  const revert = async (version: number) => {
    setReverting(version); setError(null);
    try { changed(await revertArtifact(current, version)); }
    catch { setError(STALE_ARTIFACT_MESSAGE); }
    finally { setReverting(null); }
  };

  const remove = async () => {
    setDeleting(true); setError(null); setNotice(null);
    try {
      const result = await deleteArtifact(current);
      setConfirmingDelete(false);
      if (result.warning) setNotice(ARTIFACT_EVENT_UNAVAILABLE_MESSAGE);
      // Tombstoning bumps the revision by exactly one
      // (sql_versions.tombstone_artifact); the follow-up permanent purge must
      // present that bumped revision as its expected_revision.
      const tombstone = { ...current, revision: current.revision + 1 };
      setCurrent(tombstone);
      onDeleted?.(tombstone);
      onChanged();
    } catch (rejection) {
      setError(artifactFailureMessage(rejection));
    } finally { setDeleting(false); }
  };

  const purge = async () => {
    setPurging(true); setError(null);
    try {
      await purgeArtifact(current.slug, current.revision);
      setConfirmingPurge(false); setNotice(null); setPurged(true);
    } catch (rejection) {
      setError(artifactFailureMessage(rejection, ARTIFACT_PURGE_FAILED_MESSAGE));
      setConfirmingPurge(false);
    } finally { setPurging(false); }
  };

  // Feature-map row 64's "companion-chat iteration pane": rather than a
  // second, duplicate chat surface embedded in this page, the ALREADY
  // global, always-visible chat sidebar becomes artifact-aware — same
  // mechanism CanvasContextBridge uses for workbench state (bd-vw04).
  // The user iterates through the one real chat they already have open;
  // it just now knows what they're looking at.
  const agentContextValue = useMemo(() => ({
    slug: current.slug, name: current.name, kind: current.kind,
    version: current.version, description: current.description,
    content: current.content.length > CONTEXT_CONTENT_CAP
      ? `${current.content.slice(0, CONTEXT_CONTENT_CAP)}\n…(truncated)` : current.content,
  }), [current]);
  useAgentContext({
    description:
      "The artifact the user currently has open in the Artifact detail " +
      "view. Use `artifacts_update` (slug, expected_revision, content) to " +
      "iterate on it when the user asks for changes.",
    value: agentContextValue as unknown as JsonSerializable,
  });

  return (
    <article className="rounded-xl border border-violet-500/30 bg-violet-500/[0.04] p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div><h2 className="font-medium">{current.name}</h2><p className="text-xs text-muted-foreground">{current.slug} · v{current.version} · {current.kind}</p></div>
        <div className="flex items-center gap-2">
          {!tombstoned && (
            <button type="button" onClick={() => { setConfirmingDelete(true); setError(null); }}
              className="rounded-lg border border-destructive/40 px-2.5 py-1.5 text-xs text-destructive transition-colors hover:bg-destructive/10">
              Delete
            </button>
          )}
          <button type="button" onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground">Close detail</button>
        </div>
      </div>
      {error && <div role="alert" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">{error}</div>}
      {notice && <div role="status" className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">{notice}</div>}
      {tombstoned ? (
        <section aria-label="Deleted artifact" className="rounded-lg border border-destructive/40 bg-destructive/5 p-4">
          <h3 className="text-sm font-medium text-destructive">Deleted</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            “{current.name}” ({current.slug}) is out of your library. Its history is retained until it is permanently purged.
          </p>
          {purged ? (
            <p role="status" className="mt-3 text-xs text-destructive">Permanently purged. This artifact can no longer be recovered.</p>
          ) : confirmingPurge ? (
            <div className="mt-3 space-y-2 rounded-lg border border-destructive/40 bg-background/40 p-3">
              <p className="text-xs text-destructive">Permanently purge “{current.name}” ({current.slug})? This cannot be undone.</p>
              <div className="flex gap-2">
                <button type="button" disabled={purging} onClick={() => void purge()}
                  className="rounded-md bg-destructive px-2.5 py-1.5 text-xs text-white disabled:opacity-50">
                  {purging ? "Purging…" : "Confirm permanent purge"}
                </button>
                <button type="button" onClick={() => setConfirmingPurge(false)} className="rounded-md border border-border/60 px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground">Cancel</button>
              </div>
            </div>
          ) : (
            <button type="button" onClick={() => { setConfirmingPurge(true); setError(null); }}
              className="mt-3 rounded-md border border-destructive/40 px-2.5 py-1.5 text-xs text-destructive transition-colors hover:bg-destructive/10">
              Purge permanently
            </button>
          )}
        </section>
      ) : (
        <>
          {confirmingDelete && (
            <div role="alertdialog" aria-label="Confirm artifact delete" className="mb-4 space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3">
              <p className="text-xs text-destructive">Delete “{current.name}” ({current.slug})? It leaves your library but can still be purged later.</p>
              <div className="flex gap-2">
                <button type="button" disabled={deleting} onClick={() => void remove()}
                  className="rounded-md bg-destructive px-2.5 py-1.5 text-xs text-white disabled:opacity-50">
                  {deleting ? "Deleting…" : "Confirm delete"}
                </button>
                <button type="button" onClick={() => setConfirmingDelete(false)} className="rounded-md border border-border/60 px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground">Cancel</button>
              </div>
            </div>
          )}
          <div className="mb-5"><ArtifactPreview artifact={current} onAnchorSelect={setPendingAnchor} /></div>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,0.75fr)]">
            <ArtifactEditor artifact={current} onSaved={changed} />
            <div className="space-y-6">
              <ArtifactHistory versions={versionRows} loading={versions.loading} reverting={reverting} currentVersion={current.version} onRevert={revert} />
              {versions.error && <p role="alert" className="text-xs text-destructive">Versions unavailable: {versions.error}</p>}
              <ArtifactComments
                slug={current.slug} comments={commentRows} loading={comments.loading}
                onChanged={comments.refetch} artifactContent={current.content}
                pendingAnchor={pendingAnchor} onClearAnchor={() => setPendingAnchor(null)}
              />
              {comments.error && <p role="alert" className="text-xs text-destructive">Comments unavailable: {comments.error}</p>}
            </div>
          </div>
        </>
      )}
    </article>
  );
}
