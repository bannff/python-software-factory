"use client";
import { StandaloneChat } from "@/components/chat/standalone-chat";

// /popout/chat: the chat surface in its own window. No slug route: binding a
// session by slug is unbuilt, and an unknown path 404s rather than being ignored.
export default function Page() {
  return (
    <StandaloneChat />
  );
}
