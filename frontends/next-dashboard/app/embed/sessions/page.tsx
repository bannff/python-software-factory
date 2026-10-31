"use client";
import OperationsPage from "@/components/operations/operations-page";
import { StandaloneSurface } from "@/components/layout/standalone-surface";

// Row 129 (feature-map) — /embed/sessions: the Sessions surface standalone.
export default function Page() {
  return (
    <StandaloneSurface label="Embedded sessions">
      <OperationsPage view="sessions" />
    </StandaloneSurface>
  );
}
