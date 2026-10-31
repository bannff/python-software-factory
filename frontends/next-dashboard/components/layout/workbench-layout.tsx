"use client";

import { ActivityBar } from "./activity-bar";
import { MobileNav } from "./mobile-nav";
import { Canvas } from "@/components/canvas/canvas";
import { CopilotChatSidebar } from "@/components/chat/copilot-sidebar";
import { useChatWidth } from "@/lib/hooks/use-chat-width";
import type { CanvasViewId, CanvasTab } from "@/lib/types";

interface WorkbenchLayoutProps {
  /* Workbench state */
  activeView: CanvasViewId;
  chatOpen: boolean;
  tabs: CanvasTab[];
  activeTabId: string;
  onViewChange: (view: CanvasViewId) => void;
  onToggleChat: () => void;
  onTabChange: (tabId: string) => void;
  onTabClose: (tabId: string) => void;
}

export function WorkbenchLayout(props: WorkbenchLayoutProps) {
  const { width: chatWidth, setWidth: setChatWidth } = useChatWidth();

  return (
    <div className="flex h-full min-h-0">
      {/* Desktop icon rail — hidden below md, where MobileNav takes over. */}
      <div className="hidden h-full md:flex">
        <ActivityBar activeView={props.activeView} onViewChange={props.onViewChange} />
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <MobileNav activeView={props.activeView} onViewChange={props.onViewChange} />
        <Canvas
          activeView={props.activeView}
          tabs={props.tabs}
          activeTabId={props.activeTabId}
          onTabChange={props.onTabChange}
          onTabClose={props.onTabClose}
          chatOpen={props.chatOpen}
          onToggleChat={props.onToggleChat}
          onNavigate={props.onViewChange}
        />
      </div>

      {/* Chat sidebar reserves width only at md+; below md it must not consume
          the canvas, so it is hidden rather than laid out. */}
      {props.chatOpen && (
        <div className="hidden h-full md:flex">
          <CopilotChatSidebar
            onToggle={props.onToggleChat}
            activeView={props.activeView}
            width={chatWidth}
            onResize={setChatWidth}
          />
        </div>
      )}
    </div>
  );
}
