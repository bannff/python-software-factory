"use client";
import { StandaloneView } from "@/components/layout/standalone-view";

// /popout/artifact: the Artifacts surface in its own window (no slug route yet).
export default function Page() {
  return (
    <StandaloneView view="artifacts" />
  );
}
