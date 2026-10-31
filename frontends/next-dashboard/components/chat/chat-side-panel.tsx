"use client";

import type { ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Chat right-side-panel host (the architecture upstream's chat "right
 * panel" needs — Summary / Terminal / Browser / Side / Pins / etc. tabs).
 *
 * A registry-driven tabbed container: each tab declares an id, label, and a
 * lazy `render`. Pure and presentational — the sidebar owns which tab is
 * active and whether the panel is open, so new tabs (rows 9/18/19/26/27/30)
 * plug in by appending to the `tabs` array without touching this shell.
 *
 * Scaffold: the tab strip + body + close control ship here; the initial
 * real tab is Summary (row 18's proper chat-panel home).
 */

export interface ChatPanelTab {
  id: string;
  label: string;
  render: () => ReactNode;
}

export function ChatSidePanel({ tabs, activeId, onSelect, onClose }: {
  tabs: ChatPanelTab[];
  activeId: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  if (tabs.length === 0) return null;
  const active = tabs.find((tab) => tab.id === activeId) ?? tabs[0];
  return (
    <div aria-label="Chat side panel" className="flex h-full flex-col border-l border-border/50 bg-card/10">
      <div className="flex h-9 items-center gap-1 border-b border-border/50 px-2">
        <div role="tablist" className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <button key={tab.id} type="button" role="tab" aria-selected={tab.id === active.id}
              onClick={() => onSelect(tab.id)}
              className={cn("shrink-0 rounded-md px-2.5 py-1 text-xs transition-colors",
                tab.id === active.id ? "bg-violet-500/10 text-violet-300" : "text-muted-foreground hover:bg-muted/40")}>
              {tab.label}
            </button>
          ))}
        </div>
        <button type="button" aria-label="Close panel" onClick={onClose}
          className="rounded-md p-1 text-muted-foreground hover:bg-accent/40 hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-3">{active.render()}</div>
    </div>
  );
}
