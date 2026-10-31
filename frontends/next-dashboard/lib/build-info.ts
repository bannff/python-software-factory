/**
 * Row 101 (feature-map) — build identifier.
 *
 * Populated at build time via `NEXT_PUBLIC_BUILD_ID` — Next.js inlines
 * `NEXT_PUBLIC_*` env at build, so a release pipeline sets it (e.g. a git
 * short-SHA + build timestamp). For local/unbuilt runs the var is unset, so
 * this reports "development" — an honest reflection of the running build
 * rather than a fabricated version string.
 */
export function getBuildId(): string {
  const id = process.env.NEXT_PUBLIC_BUILD_ID;
  return id && id.trim().length > 0 ? id.trim() : "development";
}
