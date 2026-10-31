"use client";
import { TerminalPanel } from "@/components/terminal/terminal-panel";
import { StandaloneSurface } from "@/components/layout/standalone-surface";

// Row 127 (feature-map) — /popout/terminal: the terminal in its own window.
// Reuses the existing TerminalPanel; onClose is a no-op in a popout (the
// window is closed by the OS, not an in-app control).
export default function Page() {
  return (
    <StandaloneSurface label="Terminal popout">
      <TerminalPanel onClose={() => undefined} />
    </StandaloneSurface>
  );
}
