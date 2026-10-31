"use client";

import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CanvasTab } from "@/lib/types";

interface CanvasTabsProps {
  tabs: CanvasTab[];
  activeTabId: string;
  onTabChange: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
}

export function CanvasTabs({ tabs, activeTabId, onTabChange, onTabClose }: CanvasTabsProps) {
  return (
    <div className="flex h-9 items-center gap-0.5 border-b border-border/50 bg-card/10 px-2 overflow-x-auto">
      {tabs.map((tab) => {
        const active = tab.id === activeTabId;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={cn(
              "group relative flex items-center gap-1.5 rounded-t-md px-3 py-1.5 text-xs font-medium transition-colors",
              active
                ? "text-foreground bg-background/50"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/30",
            )}
          >
            <span>{tab.label}</span>
            {tab.closable && (
              <span
                onClick={(e) => { e.stopPropagation(); onTabClose(tab.id); }}
                className="ml-1 rounded p-0.5 opacity-0 group-hover:opacity-100 hover:bg-accent/50 transition-opacity"
              >
                <X className="h-3 w-3" />
              </span>
            )}
            {active && (
              <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-t bg-gradient-to-r from-violet-500 to-indigo-500" />
            )}
          </button>
        );
      })}
    </div>
  );
}
