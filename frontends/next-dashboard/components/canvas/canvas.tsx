"use client";

import { Suspense, lazy } from "react";
import { usePathname } from "next/navigation";
import { PanelRight } from "lucide-react";
import { CanvasTabs } from "./canvas-tabs";
import { Refreshable } from "./refreshable";
import { NavHistoryArrows } from "@/components/layout/nav-history-arrows";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { useCopilotCanvasState } from "@/lib/hooks/use-copilot-state";
import { useSessionRuntime } from "@/lib/hooks/use-session-runtime";
import type { CanvasViewId, CanvasTab } from "@/lib/types";

const WelcomeView = lazy(() => import("./welcome-view"));
const GraphView = lazy(() => import("./graph-view"));
const TimelineViewV2 = lazy(() => import("./timeline-view-v2"));
const EvalsLeaderboardView = lazy(() => import("./evals-leaderboard-view"));
const FindingsView = lazy(() => import("./findings-view"));
const BrickViewRenderer = lazy(() => import("./brick-view-renderer"));
const MlControls = lazy(() => import("../ml/ml-controls").then((m) => ({ default: m.MlControls })));
const SandboxBanner = lazy(() => import("../sandbox/sandbox-banner").then((m) => ({ default: m.SandboxBanner })));
const GamesPanel = lazy(() => import("../games/games-panel").then((m) => ({ default: m.GamesPanel })));
const BlockchainPanel = lazy(() => import("../blockchain/blockchain-panel").then((m) => ({ default: m.BlockchainPanel })));
const GraphBrickView = lazy(() => import("./graph-brick-view"));
const RuntimeMetricsView = lazy(() => import("./runtime-metrics-view"));
const LiveView = lazy(() => import("./live-view"));
const ArtifactsView = lazy(() => import("../artifacts/artifacts-view"));
const CrewsView = lazy(() => import("../crews/crews-view"));
const SettingsView = lazy(() => import("./settings-view"));
const AgentCapabilitiesView = lazy(() => import("./agent-capabilities-view"));
const SessionsView = lazy(() => import("../operations/sessions/sessions-view"));
const SchedulesView = lazy(() => import("../operations/schedules/schedules-view"));
const LessonsView = lazy(() => import("../operations/lessons/lessons-view"));

interface CanvasProps {
  activeView: CanvasViewId;
  tabs: CanvasTab[];
  activeTabId: string;
  onTabChange: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
  chatOpen: boolean;
  onToggleChat: () => void;
  onNavigate?: (viewId: CanvasViewId) => void;
}

function CanvasLoader() {
  return (
    <div className="flex h-full items-center justify-center text-muted-foreground text-sm">
      Loading…
    </div>
  );
}

function focusId(pathname: string, kind: string): string | undefined {
  const prefix = `/${kind}/`;
  return pathname.startsWith(prefix) ? pathname.slice(prefix.length).split("/")[0] || undefined : undefined;
}

function SessionsCanvas({ pathname, chatOpen, onToggleChat }: {
  pathname: string; chatOpen: boolean; onToggleChat: () => void;
}) {
  const { agent, resumeSession, createSession } = useSessionRuntime("companion_x");
  const revealChat = () => { if (!chatOpen) onToggleChat(); };
  return <SessionsView activeThreadId={agent.threadId}
    focusSessionId={focusId(pathname, "sessions")}
    onResumeSession={async (session) => {
      if (await resumeSession(session)) revealChat();
    }}
    onCreateSession={async () => { await createSession(); revealChat(); }} />;
}

export function Canvas(props: CanvasProps) {
  const pathname = usePathname();
  const canvasState = useCopilotCanvasState();
  const workbench = useWorkbenchContext();

  return (
    <div className="flex min-h-0 flex-1 flex-col min-w-0">
      <div className="flex items-center">
        <NavHistoryArrows
          canBack={workbench.canHistoryBack}
          canForward={workbench.canHistoryForward}
          onBack={workbench.historyBack}
          onForward={workbench.historyForward}
        />
        <div className="flex-1 min-w-0">
          <CanvasTabs
            tabs={props.tabs}
            activeTabId={props.activeTabId}
            onTabChange={props.onTabChange}
            onTabClose={props.onTabClose}
          />
        </div>
        {!props.chatOpen && (
          <button
            onClick={props.onToggleChat}
            className="flex h-9 items-center gap-1.5 border-b border-border/50 bg-card/10 px-3 text-xs text-muted-foreground hover:text-foreground transition-colors"
            title="Open chat"
          >
            <PanelRight className="h-3.5 w-3.5" />
            <span>Chat</span>
          </button>
        )}
      </div>

      <div className="flex-1 overflow-auto" style={{ minHeight: 0 }}>
        <Suspense fallback={<CanvasLoader />}>
          {props.activeView === "welcome" && (
            <WelcomeView onNavigate={props.onNavigate} />
          )}
          {props.activeView === "graph" && <GraphView {...canvasState} />}
          {props.activeView === "timeline-v2" && <TimelineViewV2 {...canvasState} />}
          {props.activeView === "findings" && <FindingsView {...canvasState} />}
          {props.activeView === "evals" && <EvalsLeaderboardView onNavigate={props.onNavigate} />}
          {props.activeView === "metrics" && <RuntimeMetricsView onNavigate={props.onNavigate} />}
          {props.activeView === "ml" && <><BrickViewRenderer viewTool="ml_get_views" /><MlControls /></>}
          {props.activeView === "games" && <Refreshable label="games"><><GamesPanel /><GraphBrickView viewTool="games_get_views" defaultEntityType="GameSession" onNavigate={props.onNavigate} /></></Refreshable>}
          {props.activeView === "blockchain" && <Refreshable label="blockchain"><><BlockchainPanel /><GraphBrickView viewTool="blockchain_get_views" defaultEntityType="Transaction" onNavigate={props.onNavigate} /></></Refreshable>}
          {props.activeView === "sandbox" && <Refreshable label="sandbox"><><SandboxBanner /><GraphBrickView viewTool="sandbox_get_views" defaultEntityType="ToolInvocation" onNavigate={props.onNavigate} /></></Refreshable>}
          {props.activeView === "capabilities" && <AgentCapabilitiesView />}
          {props.activeView === "sessions" && <SessionsCanvas pathname={pathname}
            chatOpen={props.chatOpen} onToggleChat={props.onToggleChat} />}
          {props.activeView === "schedules" && <SchedulesView focusScheduleId={focusId(pathname, "schedules")} />}
          {props.activeView === "lessons" && <LessonsView focusLessonId={focusId(pathname, "lessons")} />}
          {props.activeView === "artifacts" && <ArtifactsView />}
          {props.activeView === "crews" && <CrewsView />}
          {props.activeView === "settings" && <SettingsView />}
          {props.activeView === "live" && <LiveView />}
        </Suspense>
      </div>
    </div>
  );
}
