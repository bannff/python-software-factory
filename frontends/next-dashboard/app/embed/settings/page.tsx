"use client";
import OperationsPage from "@/components/operations/operations-page";
import { StandaloneSurface } from "@/components/layout/standalone-surface";

// Row 130 (feature-map) — /embed/settings: the Settings surface standalone.
export default function Page() {
  return (
    <StandaloneSurface label="Embedded settings">
      <OperationsPage view="settings" />
    </StandaloneSurface>
  );
}
