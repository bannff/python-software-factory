"use client";

import { Suspense, lazy } from "react";
import { useSessionRuntime } from "@/lib/hooks/use-session-runtime";

const ArtifactsView = lazy(() => import("../artifacts/artifacts-view"));
const SettingsView = lazy(() => import("../canvas/settings-view"));
const SessionsView = lazy(() => import("../operations/sessions/sessions-view"));

export type StandaloneViewId = "artifacts" | "settings" | "sessions";

function SessionsEmbed() {
  const { agent, resumeSession, createSession } = useSessionRuntime("companion_x");
  return <SessionsView activeThreadId={agent.threadId}
    onResumeSession={async (session) => { await resumeSession(session); }}
    onCreateSession={async () => { await createSession(); }} />;
}

/**
 * One workbench view rendered on its own, for the popout/embed routes. It
 * mounts the view component directly: no activity bar, tab strip or chat, so
 * a host embedding it gets the surface and nothing else.
 */
export function StandaloneView({ view }: { view: StandaloneViewId }) {
  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Loading…</div>}>
        {view === "artifacts" && <ArtifactsView />}
        {view === "settings" && <SettingsView />}
        {view === "sessions" && <SessionsEmbed />}
      </Suspense>
    </div>
  );
}
