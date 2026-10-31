"use client";

import {
  Search,
  Network,
  GitBranch,
  Shield,
  Beaker,
  BarChart3,
  Brain,
  Gamepad2,
  Link2,
  Container,
  LayoutGrid,
  Settings,
  MessagesSquare,
  Blocks,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useActiveBackgroundRunCount } from "@/lib/hooks/use-active-background-run-count";
import { syncCanvasRoute } from "@/lib/canvas-routes";
import type { CanvasViewId } from "@/lib/types";

interface ActivityBarProps {
  activeView: CanvasViewId;
  onViewChange: (view: CanvasViewId) => void;
}

type NavItem = { id: CanvasViewId; icon: typeof Search; label: string };
type NavGroup = { caption: string; items: NavItem[] };

export const CAPABILITY_VIEWS = new Set<CanvasViewId>([
  "capabilities", "crews", "schedules", "artifacts", "lessons",
]);

/**
 * Divider-grouped destinations. M7.5 collapses Crews, Schedules, Artifacts,
 * and Lessons under one Agent Capabilities icon; direct child routes still
 * highlight that parent. ``System`` remains bottom-pinned.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    caption: "Operations",
    items: [
      { id: "welcome", icon: Search, label: "Investigate" },
      { id: "live", icon: LayoutGrid, label: "Live" },
      { id: "sessions", icon: MessagesSquare, label: "Sessions" },
      { id: "capabilities", icon: Blocks, label: "Agent Capabilities" },
      { id: "timeline-v2", icon: GitBranch, label: "Timeline" },
      { id: "sandbox", icon: Container, label: "Sandbox" },
    ],
  },
  {
    caption: "Analysis",
    items: [
      { id: "graph", icon: Network, label: "Graph" },
      { id: "findings", icon: Shield, label: "Findings" },
      { id: "evals", icon: Beaker, label: "Evals" },
      { id: "metrics", icon: BarChart3, label: "Metrics" },
    ],
  },
  {
    caption: "Intelligence",
    items: [
      { id: "ml", icon: Brain, label: "ML" },
      { id: "games", icon: Gamepad2, label: "Games" },
      { id: "blockchain", icon: Link2, label: "Blockchain" },
    ],
  },
  {
    caption: "System",
    items: [{ id: "settings", icon: Settings, label: "Settings" }],
  },
];

function NavButton({ item, caption, active, onSelect, badge }: {
  item: NavItem; caption: string; active: boolean; onSelect: () => void; badge?: number;
}) {
  const Icon = item.icon;
  return (
    <button
      onClick={onSelect}
      title={item.label}
      aria-label={badge ? `${item.label} (${badge} running)` : item.label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-10 w-10 items-center justify-center rounded-lg transition-all duration-200",
        active
          ? "bg-gradient-to-br from-violet-500/20 to-indigo-500/20 text-violet-400 shadow-sm shadow-violet-500/10"
          : "text-muted-foreground hover:text-foreground hover:bg-accent/50",
      )}
    >
      <Icon className="h-[18px] w-[18px]" />
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-r bg-violet-500" />
      )}
      {!!badge && (
        <span
          data-testid="nav-badge"
          className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-violet-500 px-1 text-[9px] font-medium leading-none text-white"
        >
          {badge > 9 ? "9+" : badge}
        </span>
      )}
      <span
        role="tooltip"
        className="absolute left-12 z-50 hidden rounded-md bg-popover px-2 py-1 text-popover-foreground shadow-md group-hover:block group-focus-visible:block whitespace-nowrap"
      >
        <span className="block text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          {caption}
        </span>
        <span className="text-xs">{item.label}</span>
      </span>
    </button>
  );
}

export function ActivityBar({ activeView, onViewChange }: ActivityBarProps) {
  const select = (id: CanvasViewId) => {
    syncCanvasRoute(id);
    onViewChange(id);
  };
  const activeRunCount = useActiveBackgroundRunCount();
  return (
    <nav
      aria-label="Primary"
      className="flex h-full w-12 flex-col items-center border-r border-border/50 bg-card/20 backdrop-blur-md py-3 gap-1"
    >
      {NAV_GROUPS.map((group, index) => (
        <div
          key={group.caption}
          role="group"
          aria-label={group.caption}
          className={cn(
            "flex flex-col items-center gap-1",
            group.caption === "System" && "mt-auto",
          )}
        >
          {index > 0 && (
            <span aria-hidden className="my-1 h-px w-6 rounded bg-border/50" />
          )}
          {group.items.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              caption={group.caption}
              active={activeView === item.id
                || (item.id === "capabilities" && CAPABILITY_VIEWS.has(activeView))}
              onSelect={() => select(item.id)}
              badge={item.id === "sessions" ? activeRunCount : undefined}
            />
          ))}
        </div>
      ))}
    </nav>
  );
}
