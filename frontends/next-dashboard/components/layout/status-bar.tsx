"use client";

import { Terminal } from "lucide-react";
import { useSyncExternalStore } from "react";
import { useHealth } from "@/lib/hooks/use-health";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { getTerminalSessions, subscribeTerminalSessions } from "@/lib/terminal-store";
import { ConnectionItem, BrickItem, ToolItem, GitItem } from "./status-bar-items";
import { SubagentsItem } from "./subagents-item";
import { MonitorItem } from "./monitor-item";
import { CopilotItem } from "./copilot-status-item";
import { ThemeToggle } from "./theme-toggle";

export function StatusBar() {
  const workbench = useWorkbenchContext();
  const terminalSessions = useSyncExternalStore(
    subscribeTerminalSessions, getTerminalSessions, getTerminalSessions,
  );
  const { connected, status, totalTools, brickCount, healthyBricks, bricks, lastChecked } =
    useHealth();

  return (
    <footer className="flex h-6 items-center justify-between border-t border-border/50 bg-card/30 backdrop-blur-md px-3 text-[11px]">
      <div className="flex items-center gap-3">
        <ConnectionItem connected={connected} status={status} lastChecked={lastChecked} />

        {brickCount !== null && (
          <>
            <Sep />
            <BrickItem brickCount={brickCount} healthyBricks={healthyBricks} bricks={bricks} />
          </>
        )}

        {totalTools !== null && (
          <>
            <Sep />
            <ToolItem totalTools={totalTools} />
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button type="button" onClick={workbench.toggleTerminal}
          aria-pressed={workbench.terminalOpen} aria-label="Toggle Terminal"
          className="flex items-center gap-1 text-muted-foreground hover:text-foreground">
          <Terminal className="h-3 w-3" /><span>Terminal</span>
          {terminalSessions.length > 0 && <span>{terminalSessions.length}</span>}
        </button>
        <Sep />
        <SubagentsItem />
        <Sep />
        <MonitorItem />
        <Sep />
        <CopilotItem />
        <Sep />
        <GitItem />
        <ThemeToggle />
      </div>
    </footer>
  );
}

function Sep() {
  return <div className="h-3 w-px bg-border/50" />;
}
