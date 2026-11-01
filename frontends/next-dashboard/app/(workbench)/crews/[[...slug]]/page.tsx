"use client";

import { useEffect } from "react";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { WorkbenchLayout } from "@/components/layout/workbench-layout";

/**
 * Direct ``/crews`` (and ``/crews/<id>``) entry. Mirrors the Artifacts route:
 * the workbench renders the same layout and we force the Crews canvas view on
 * mount so a deep link lands on the gallery.
 */
export default function CrewsPage() {
  const workbench = useWorkbenchContext();
  useEffect(() => { workbench.switchView("crews"); }, [workbench.switchView]);
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
