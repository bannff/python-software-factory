"use client";

import { Activity, CalendarClock, MessagesSquare, PlugZap, Wrench } from "lucide-react";
import { useHealth } from "@/lib/hooks/use-health";
import { useSessionList } from "@/lib/hooks/use-session-list";
import { useSchedules } from "@/lib/hooks/use-schedules";
import { useOptionalWorkbenchContext } from "@/lib/workbench-context";
import { useDisplayPreferences } from "@/components/settings/use-display-preferences";
import { useExternalServerCount } from "@/components/connections/use-external-server-count";
import type { CanvasViewId } from "@/lib/types";

/**
 * Settings → Overview: live health hero, stat cards that drill into the
 * surface that owns each number, and the owner's saved Display choices read
 * from the durable preference (never hardcoded). Memory/usage drill-ins are
 * deliberately absent until M7.7 ships those surfaces.
 */
export default function OverviewPanel() {
  const health = useHealth();
  const { sessions, loading: sessionsLoading } = useSessionList(false);
  const { schedules, loading: schedulesLoading } = useSchedules();
  const external = useExternalServerCount();
  const { preferences, loading: prefsLoading } = useDisplayPreferences();
  const workbench = useOptionalWorkbenchContext();

  const checking = health.lastChecked === null;
  const tone = checking ? "bg-muted-foreground/40" : health.connected ? "bg-emerald-400" : "bg-destructive";
  const headline = checking ? "Checking the gateway…" : health.connected ? "Companion X is connected" : "Gateway unreachable";
  const active = schedules.filter((item) => item.state === "active").length;

  const go = (view: CanvasViewId, path?: string) => () => {
    workbench?.switchView(view);
    if (path && typeof window !== "undefined") window.history.pushState({}, "", path);
  };

  return <div className="grid gap-4">
    <section aria-labelledby="overview-health" className="rounded-lg border border-border/50 bg-card/30 p-5">
      <div className="flex items-center gap-3">
        <span aria-hidden className={`h-3 w-3 rounded-full ${tone} ${health.connected ? "animate-pulse" : ""}`} />
        <h2 id="overview-health" className="text-base font-semibold">{headline}</h2>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {health.brickCount != null ? `${health.healthyBricks ?? 0} of ${health.brickCount} bricks healthy` : "Brick health not reported yet"}
        {health.lastChecked !== null && ` · checked ${new Date(health.lastChecked).toLocaleTimeString()}`}
      </p>
    </section>

    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="list" aria-label="Runtime at a glance">
      <Stat icon={Wrench} label="Tools available" value={health.totalTools} hint="Agent Capabilities → Connections" onOpen={go("capabilities", "/capabilities?tab=connections")} />
      <Stat icon={PlugZap} label="External MCP servers" value={external.count} hint={external.mounted != null ? `${external.mounted} mounted` : "Add your own servers"} onOpen={go("capabilities", "/capabilities?tab=connections")} />
      <Stat icon={MessagesSquare} label="Sessions" value={sessionsLoading ? null : sessions.length} hint="Open the Sessions list" onOpen={go("sessions")} />
      <Stat icon={CalendarClock} label="Schedules" value={schedulesLoading ? null : schedules.length} hint={schedulesLoading ? "Loading…" : `${active} active`} onOpen={go("schedules")} />
    </div>

    <section aria-labelledby="overview-display" className="rounded-lg border border-border/50 bg-card/30 p-5">
      <div className="flex items-start justify-between gap-3">
        <div><h2 id="overview-display" className="text-sm font-semibold">Your display</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Saved per owner. Change them in Display.</p></div>
        <button type="button" onClick={go("settings", "/settings?section=display")}
          className="text-xs text-violet-300 hover:text-violet-200">Open Display →</button>
      </div>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
        <Row label="Theme" value={prefsLoading ? "…" : preferences.theme} />
        <Row label="Density" value={prefsLoading ? "…" : preferences.density} />
        <Row label="Language" value={prefsLoading ? "…" : preferences.language} />
      </dl>
    </section>
  </div>;
}

function Stat({ icon: Icon, label, value, hint, onOpen }: {
  icon: typeof Activity; label: string; value: number | null | undefined; hint: string; onOpen: () => void;
}) {
  return <button type="button" role="listitem" onClick={onOpen} aria-label={`${label}: ${value ?? "unknown"}. ${hint}`}
    className="rounded-lg border border-border/50 bg-card/30 p-4 text-left transition-colors hover:border-violet-400/50 hover:bg-accent/30">
    <div className="flex items-center justify-between text-muted-foreground"><span className="text-xs">{label}</span><Icon className="h-4 w-4" /></div>
    <strong className="mt-2 block text-2xl font-semibold text-foreground">{value ?? "—"}</strong>
    <span className="mt-1 block text-[11px] text-muted-foreground">{hint}</span>
  </button>;
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md border border-border/30 px-3 py-2">
    <dt className="text-[11px] text-muted-foreground">{label}</dt>
    <dd className="m-0 font-medium capitalize text-foreground/90">{value}</dd>
  </div>;
}
