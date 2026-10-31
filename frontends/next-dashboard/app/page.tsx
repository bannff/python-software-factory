"use client";

import { useWorkbenchContext } from "@/lib/workbench-context";
import { WorkbenchLayout } from "@/components/layout/workbench-layout";

export default function Home() {
  const workbench = useWorkbenchContext();

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
