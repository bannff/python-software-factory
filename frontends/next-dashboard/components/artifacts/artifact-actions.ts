import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";
import type { Artifact, ArtifactFolder } from "./artifact-types";

function artifactFrom(raw: unknown): Artifact {
  const data = unwrapToolData(raw) as { result?: { artifact?: Artifact } } | undefined;
  const artifact = data?.result?.artifact;
  if (!artifact) throw new Error("Artifact mutation returned no record");
  return artifact;
}

function folderFrom(raw: unknown): ArtifactFolder {
  const data = unwrapToolData(raw) as { folder?: ArtifactFolder } | undefined;
  const folder = data?.folder;
  if (!folder) throw new Error("Folder mutation returned no record");
  return folder;
}

export async function listFolders(): Promise<ArtifactFolder[]> {
  const data = unwrapToolData(await callTool("artifacts_folder_list", {})) as { folders?: unknown };
  return Array.isArray(data?.folders) ? data.folders as ArtifactFolder[] : [];
}

export async function createFolder(name: string, parentId: string | null): Promise<ArtifactFolder> {
  return folderFrom(await callTool("artifacts_folder_create", {
    name, ...(parentId ? { parent_id: parentId } : {}),
  }));
}

export async function renameFolder(folder: ArtifactFolder, name: string): Promise<ArtifactFolder> {
  return folderFrom(await callTool("artifacts_folder_rename", {
    folder_id: folder.id, expected_revision: folder.revision, name,
  }));
}

export async function moveFolder(folder: ArtifactFolder, parentId: string | null): Promise<ArtifactFolder> {
  return folderFrom(await callTool("artifacts_folder_move", {
    folder_id: folder.id, expected_revision: folder.revision,
    ...(parentId ? { parent_id: parentId } : {}),
  }));
}

export async function deleteFolder(folder: ArtifactFolder): Promise<void> {
  await callTool("artifacts_folder_delete", {
    folder_id: folder.id, expected_revision: folder.revision,
  });
}

export async function moveArtifactToFolder(
  artifact: Artifact, folderId: string | null,
): Promise<Artifact> {
  const data = unwrapToolData(await callTool("artifacts_move", {
    slug: artifact.slug, expected_revision: artifact.revision,
    ...(folderId ? { folder_id: folderId } : {}),
  })) as { artifact?: Artifact };
  if (!data?.artifact) throw new Error("Artifact move returned no record");
  return data.artifact;
}

export async function saveArtifact(input: {
  name: string; content: string; kind: Artifact["kind"];
  description?: string; tags?: string[];
}): Promise<Artifact> {
  return artifactFrom(await callTool("artifacts_save", {
    name: input.name, content: input.content, kind: input.kind,
    description: input.description ?? "", tags: input.tags ?? [],
  }));
}

export async function updateArtifact(
  artifact: Artifact, content: string,
): Promise<Artifact> {
  return artifactFrom(await callTool("artifacts_update", {
    slug: artifact.slug,
    expected_revision: artifact.revision,
    content,
  }));
}

export async function revertArtifact(
  artifact: Artifact, version: number,
): Promise<Artifact> {
  return artifactFrom(await callTool("artifacts_revert", {
    slug: artifact.slug,
    expected_revision: artifact.revision,
    version,
  }));
}

export async function postArtifactComment(
  slug: string, body: string, anchorText?: string | null,
): Promise<void> {
  await callTool("artifacts_post_comment", {
    slug, body, ...(anchorText ? { anchor_text: anchorText } : {}),
  });
}

export async function markArtifactCommentReview(
  slug: string, commentId: string,
): Promise<void> {
  await callTool("artifacts_mark_comment_review", {
    slug,
    comment_id: commentId,
  });
}

export const STALE_ARTIFACT_MESSAGE =
  "This artifact changed since it was opened. Refresh the latest revision and try again.";

export const ARTIFACT_DELETE_FAILED_MESSAGE =
  "This artifact could not be deleted — it may have changed or already been removed. Refresh the library and try again.";

export const ARTIFACT_NOT_FOUND_MESSAGE = "This artifact no longer exists.";

export const ARTIFACT_PURGE_FAILED_MESSAGE =
  "This artifact could not be purged. Refresh the library and try again.";

/** Purge is refused by the backend until the human-only authoring tools are on. */
export const ARTIFACT_PURGE_DISABLED_MESSAGE =
  "Permanent purge is unavailable: the artifact authoring tools are off. Set ARTIFACTS_ENABLE_AUTHORING_TOOLS to enable purging.";

export const ARTIFACT_HUMAN_REQUIRED_MESSAGE =
  "Permanent purge requires a human actor; agent sessions cannot purge artifacts.";

/** Tombstoning succeeded but the ``artifact.deleted`` event was not published. */
export const ARTIFACT_EVENT_UNAVAILABLE_MESSAGE =
  "Deleted, but the artifact.deleted event could not be published (artifact_event_unavailable) — downstream consumers were not notified.";

export type ArtifactDeletion = { slug: string; warning: string | null };

/**
 * Delete = soft delete (`artifacts_tombstone`): the artifact leaves the
 * library, keeps its history, and bumps the revision. It is NOT the
 * permanent `artifacts_purge` — the two are deliberately separate actions.
 */
export async function deleteArtifact(artifact: Artifact): Promise<ArtifactDeletion> {
  const data = unwrapToolData(await callTool("artifacts_tombstone", {
    slug: artifact.slug, expected_revision: artifact.revision,
  })) as { slug?: unknown; tombstoned?: unknown; warning?: unknown } | undefined;
  if (data?.tombstoned !== true) throw new Error("artifact_delete_failed");
  return {
    slug: typeof data.slug === "string" ? data.slug : artifact.slug,
    warning: typeof data.warning === "string" ? data.warning : null,
  };
}

/**
 * Purge = `artifacts_purge`, permanently removing an already-tombstoned
 * artifact. Requires a human actor AND the human-only authoring tools
 * (`ARTIFACTS_ENABLE_AUTHORING_TOOLS`); the backend refuses with
 * `artifact_human_required` / `authoring_disabled` otherwise.
 */
export async function purgeArtifact(slug: string, expectedRevision: number): Promise<void> {
  const data = unwrapToolData(await callTool("artifacts_purge", {
    slug, expected_revision: expectedRevision,
  })) as { deleted?: unknown } | undefined;
  if (data?.deleted !== true) throw new Error("artifact_purge_failed");
}

/**
 * Translate a delete/purge rejection into operator-readable copy. The typed
 * `artifact_human_required` / `authoring_disabled` codes arrive verbatim; a
 * revision conflict and a missing artifact both collapse to the transport's
 * `tool_execution_failed`, so those share one honest message.
 */
export function artifactFailureMessage(
  error: unknown, fallback: string = ARTIFACT_DELETE_FAILED_MESSAGE,
): string {
  const raw = error instanceof Error ? error.message : String(error);
  if (raw.includes("artifact_human_required")) return ARTIFACT_HUMAN_REQUIRED_MESSAGE;
  if (raw.includes("authoring_disabled")) return ARTIFACT_PURGE_DISABLED_MESSAGE;
  if (raw.includes("artifact_not_found")) return ARTIFACT_NOT_FOUND_MESSAGE;
  if (raw.includes("artifact_revision_conflict")) return STALE_ARTIFACT_MESSAGE;
  return fallback;
}
