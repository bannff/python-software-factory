"use client";

import { useEffect } from "react";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { WorkbenchLayout } from "@/components/layout/workbench-layout";

export default function ArtifactsPage() {
  const workbench = useWorkbenchContext();
  useEffect(() => { workbench.switchView("artifacts"); }, [workbench.switchView]);
  return (
    <WorkbenchLayout
      activeView={workbench.activeView}
      chatOpen={workbench.chatOpen}
      tabs={workbench.tabs}
      activeTabId={workbench.activeTabId}
      onViewChange={workbench.switchView}
      onToggleChat={workbench.toggleChat}
      onTabChange={workbench.setActiveTabId}
      onTabClose={workbench.closeTab}
    />
  );
}
