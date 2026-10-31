"use client";

import { useEffect } from "react";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { WorkbenchLayout } from "@/components/layout/workbench-layout";
import type { CanvasViewId } from "@/lib/types";

export default function OperationsPage({ view }: { view: CanvasViewId }) {
  const workbench = useWorkbenchContext();
  useEffect(() => { workbench.switchView(view); }, [view, workbench.switchView]);
  return <WorkbenchLayout activeView={workbench.activeView} chatOpen={workbench.chatOpen}
    tabs={workbench.tabs} activeTabId={workbench.activeTabId}
    onViewChange={workbench.switchView} onToggleChat={workbench.toggleChat}
    onTabChange={workbench.setActiveTabId} onTabClose={workbench.closeTab} />;
}
