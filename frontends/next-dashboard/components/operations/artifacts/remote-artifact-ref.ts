/**
 * Row 66 (feature-map) — Remote artifacts: provider-hosted docs browsed and
 * commented in place at `/artifacts/remote/:provider/:externalId`.
 *
 * This is the reference model that surface needs: validate a
 * (provider, externalId) pair against the known provider set and build the
 * canonical route. Pure/self-contained — the provider integrations that
 * actually fetch + render + comment on a remote doc are the deferred backend
 * half (no remote-artifact provider exists in Companion-X yet).
 */

export const REMOTE_PROVIDERS = ["gdocs", "gdrive", "notion", "confluence"] as const;
export type RemoteProvider = (typeof REMOTE_PROVIDERS)[number];

export interface RemoteArtifactRef {
  provider: RemoteProvider;
  externalId: string;
}

// externalId must be a single safe path segment — no slashes, spaces, or
// traversal that could escape the `/artifacts/remote/...` route.
const SAFE_EXTERNAL_ID = /^[A-Za-z0-9._-]+$/;

function isProvider(value: string): value is RemoteProvider {
  return (REMOTE_PROVIDERS as readonly string[]).includes(value);
}

/** Validate a (provider, externalId) pair; returns null when unusable. */
export function parseRemoteArtifactRef(
  provider: string,
  externalId: string,
): RemoteArtifactRef | null {
  const p = provider.trim().toLowerCase();
  const id = externalId.trim();
  if (!isProvider(p) || !SAFE_EXTERNAL_ID.test(id)) return null;
  return { provider: p, externalId: id };
}

/** Canonical in-app route for a remote artifact. */
export function remoteArtifactPath(ref: RemoteArtifactRef): string {
  return `/artifacts/remote/${ref.provider}/${encodeURIComponent(ref.externalId)}`;
}
