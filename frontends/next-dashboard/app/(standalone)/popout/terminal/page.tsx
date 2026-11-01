"use client";
import { TerminalPanel } from "@/components/terminal/terminal-panel";

// Row 127 (feature-map) — /popout/terminal: the terminal in its own window.
// Reuses TerminalPanel without onClose (the window is closed by the OS).
export default function Page() {
  return (
    <TerminalPanel />
  );
}
