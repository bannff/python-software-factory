"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import AgentTemplatesView from "@/components/agents/agent-templates-view";
import ArtifactsView from "@/components/artifacts/artifacts-view";
import ConnectionsView from "@/components/connections/connections-view";
import HooksView from "@/components/hooks/hooks-view";
import CrewsView from "@/components/crews/crews-view";
import KnowledgeView from "@/components/operations/knowledge/knowledge-view";
import LessonsView from "@/components/operations/lessons/lessons-view";
import MemoryView from "@/components/operations/memory/memory-view";
import PromptsView from "@/components/prompts/prompts-view";
import ProjectsView from "@/components/operations/projects/projects-view";
import SchedulesView from "@/components/operations/schedules/schedules-view";
import SkillsView from "@/components/skills/skills-view";
import SteeringView from "@/components/steering/steering-view";
import WorkflowLibraryView from "@/components/operations/workflows/workflow-library-view";

const TABS = [
  ["crews", "Crews"], ["agents", "Agent Templates"],
  ["connections", "Connections"], ["skills", "Skills"],
  ["steering", "Steering"], ["hooks", "Hooks"], ["prompts", "Prompts"],
  ["projects", "Projects"],
  ["schedules", "Schedules"], ["artifacts", "Artifacts"], ["memory", "Memory"],
  ["knowledge", "Knowledge"], ["workflows", "Workflows"], ["lessons", "Lessons"],
] as const;
type TabId = (typeof TABS)[number][0];
const IDS = new Set<string>(TABS.map(([id]) => id));

export default function AgentCapabilitiesView() {
  const requested = useSearchParams().get("tab");
  const [active, setActive] = useState<TabId>(
    requested && IDS.has(requested) ? requested as TabId : "crews",
  );
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  useEffect(() => {
    if (requested && IDS.has(requested)) setActive(requested as TabId);
  }, [requested]);

  const select = (id: TabId) => {
    setActive(id);
    window.history.pushState({}, "", `/capabilities?tab=${id}`);
  };
  const onKeys = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex(([id]) => id === active);
    const delta = event.key === "ArrowDown" || event.key === "ArrowRight" ? 1
      : event.key === "ArrowUp" || event.key === "ArrowLeft" ? -1 : 0;
    if (!delta && !["Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1
      : (index + delta + TABS.length) % TABS.length;
    select(TABS[next][0]);
    refs.current[TABS[next][0]]?.focus();
  };

  const label = TABS.find(([id]) => id === active)?.[1] ?? active;
  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="capabilities-title">
      <header><p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Workspace</p>
        <h1 id="capabilities-title" className="mt-1 text-2xl font-semibold">Agent Capabilities</h1>
        <p className="mt-1 text-sm text-muted-foreground">Configure what your agents can use and manage.</p></header>
      <div className="grid min-h-0 flex-1 gap-5 md:grid-cols-[13rem_minmax(0,1fr)]">
        <div role="tablist" aria-label="Agent Capabilities sections" onKeyDown={onKeys}
          className="flex gap-1 overflow-x-auto md:flex-col">
          {TABS.map(([id, tabLabel]) => <button key={id} ref={(node) => { refs.current[id] = node; }}
            type="button" role="tab" aria-selected={active === id} tabIndex={active === id ? 0 : -1}
            onClick={() => select(id)} className={cn("min-h-10 shrink-0 rounded-md px-3 text-left text-sm",
              active === id ? "bg-violet-500/15 text-violet-300" : "text-muted-foreground hover:bg-accent/40 hover:text-foreground")}>{tabLabel}</button>)}
        </div>
        <div role="tabpanel" aria-label={label} tabIndex={0} className="min-h-0 min-w-0 overflow-y-auto">
          {active === "crews" && <CrewsView />}
          {active === "agents" && <AgentTemplatesView />}
          {active === "connections" && <ConnectionsView />}
          {active === "skills" && <SkillsView />}
          {active === "steering" && <SteeringView />}
          {active === "hooks" && <HooksView />}
          {active === "prompts" && <PromptsView />}
          {active === "projects" && <ProjectsView />}
          {active === "schedules" && <SchedulesView />}
          {active === "artifacts" && <ArtifactsView />}
          {active === "memory" && <MemoryView />}
          {active === "knowledge" && <KnowledgeView />}
          {active === "workflows" && <WorkflowLibraryView />}
          {active === "lessons" && <LessonsView />}
        </div>
      </div>
    </section>
  );
}
