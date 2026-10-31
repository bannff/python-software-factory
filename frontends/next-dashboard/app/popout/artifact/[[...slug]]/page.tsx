"use client";
import OperationsPage from "@/components/operations/operations-page";
import { StandaloneSurface } from "@/components/layout/standalone-surface";

// Row 126 (feature-map) — /popout/artifact/:slug: the Artifacts surface in a
// standalone popout window. Slug-focus (open one artifact directly) is a
// deferred refinement; this ships the standalone Artifacts surface.
export default function Page() {
  return (
    <StandaloneSurface label="Artifact popout">
      <OperationsPage view="artifacts" />
    </StandaloneSurface>
  );
}
