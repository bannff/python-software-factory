"use client";
import { StandaloneChat } from "@/components/chat/standalone-chat";
import { StandaloneSurface } from "@/components/layout/standalone-surface";

// Row 128 (feature-map) — /embed/chat/:slug: the chat surface embedded in a
// host. Slug session-binding is a deferred refinement.
export default function Page() {
  return (
    <StandaloneSurface label="Embedded chat">
      <StandaloneChat />
    </StandaloneSurface>
  );
}
