"use client";

import { cn } from "@/lib/utils";
import { useHealth } from "@/lib/hooks/use-health";

/**
 * Row 111 (feature-map) — `agent-backend`, homed in Settings → Developer.
 * Upstream lets the operator pick an agent-harness backend and hosts the
 * Kiro sign-in card while KAS is offered. Companion-X runs a SINGLE built-in
 * harness — LangChain/LangGraph over MCP v2 (Track B rails) — with no
 * pluggable ACP/KAS backend and no Kiro sign-in, so this is an honest
 * status panel: the live harness + its transport health. (KiroCrew-identity
 * backend switching is out of scope / M8 rebrand territory.)
 */
export function AgentBackendPanel() {
  const { connected, status } = useHealth();
  return (
    <div className="mt-4 rounded-md border border-border/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium">Agent backend</h3>
          <p className="mt-1 text-xs text-muted-foreground">The live agent harness for this instance.</p>
        </div>
        <span className={cn("shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium",
          connected ? "bg-emerald-500/10 text-emerald-400" : "bg-destructive/10 text-destructive")}>
          {connected ? "live" : status}
        </span>
      </div>
      <dl className="mt-3 grid gap-1.5 text-xs">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Harness</dt>
          <dd className="font-medium">LangChain / LangGraph</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">Transport</dt>
          <dd className="font-medium">MCP v2</dd>
        </div>
      </dl>
      <p className="mt-3 rounded-md border border-border/40 bg-muted/20 p-2 text-[11px] text-muted-foreground">
        Companion-X runs one built-in harness; pluggable ACP/KAS backends and Kiro sign-in are not applicable.
      </p>
    </div>
  );
}
