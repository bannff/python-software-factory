"use client";
import { StandaloneChat } from "@/components/chat/standalone-chat";
import { StandaloneSurface } from "@/components/layout/standalone-surface";

// Row 125 (feature-map) — /popout/chat/:slug: the chat surface in a popout
// window. Slug session-binding is a deferred refinement.
export default function Page() {
  return (
    <StandaloneSurface label="Chat popout">
      <StandaloneChat />
    </StandaloneSurface>
  );
}
