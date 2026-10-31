"use client";

import { useWorkbenchContext } from "@/lib/workbench-context";
import { TerminalPanel } from "./terminal-panel";

export default function TerminalDock() {
  const workbench = useWorkbenchContext();
  if (!workbench.terminalOpen) return null;
  return <TerminalPanel onClose={workbench.toggleTerminal} />;
}
