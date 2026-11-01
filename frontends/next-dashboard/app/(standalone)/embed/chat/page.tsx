"use client";
import { StandaloneChat } from "@/components/chat/standalone-chat";

// /embed/chat: the chat surface embedded in a host (no slug route yet).
export default function Page() {
  return (
    <StandaloneChat />
  );
}
