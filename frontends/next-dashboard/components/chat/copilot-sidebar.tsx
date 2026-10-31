"use client";

import { useMemo, useRef, useState, type ReactElement } from "react";
import { PanelRightClose } from "lucide-react";
import { PanelRight as PanelRightIcon } from "lucide-react";
import { CopilotChat } from "@copilotkit/react-core/v2";
import { useAgent } from "@copilotkit/react-core/v2";
import type { Message } from "@ag-ui/core";
import { useLiveToolStream } from "@/lib/hooks/use-live-tool-stream";
import { cn } from "@/lib/utils";
import { ChatResizeHandle } from "./chat-resize-handle";
import { makeCollapsibleComposerInput } from "./composer-collapse";
import { PinnedPromptBanner, latestUserPrompt } from "./pinned-prompt-banner";
import { TurnMinimap, turnsFromMessages } from "./turn-minimap";
import { ChatSidePanel, type ChatPanelTab } from "./chat-side-panel";
import { mergeContributedTabs } from "./panel-tab-registry";
import { ChatSummaryTab } from "./chat-summary-tab";
import { ChatPinsTab } from "./chat-pins-tab";
import { ChatFilesTab } from "./chat-files-tab";
import { ChatSideTab } from "./chat-side-tab";
import { ChatBrowserTab } from "./chat-browser-tab";
import { AskAboutThisOverlay } from "./ask-about-this";
import { buildAskAboutPrompt } from "@/lib/chat/side-chat";
import { useChatCallbacks } from "@/lib/copilotkit/chat-callbacks";
import { useChatPreferences } from "@/components/settings/use-chat-preferences";
import { pickHeaderTool } from "@/lib/copilotkit/tool-friendly-names";
import { ChatDisclaimer } from "@/lib/copilotkit/chat-disclaimer";
import {
  makeAssistantMessageSlot,
  makeUserMessageSlot,
} from "@/lib/copilotkit/feedback-message-slot";
import { SubAgentGroupedView } from "@/lib/copilotkit/sub-agent-group";
import { ReasoningSlot } from "@/lib/copilotkit/reasoning-slot";
import { StopAwareSendButton } from "@/lib/copilotkit/stop-button";
import { McpConnectionNotice, McpReadyTextArea } from "@/lib/copilotkit/mcp-connection-gate";
import { CodeBlockMarkdownRenderer } from "@/lib/copilotkit/markdown-renderer";
import { PersonaPalette } from "./persona-palette";
import { ModelPicker } from "./model-picker";
import { SessionDeck } from "./session-deck";
import { SteerDeliveryListener } from "@/lib/copilotkit/steer-delivery";
import type { CanvasViewId } from "@/lib/types";
const VIEW_LABELS: Record<CanvasViewId, string> = {
  welcome: "Welcome",
  graph: "Graph",
  "timeline-v2": "Timeline",
  findings: "Findings",
  evals: "Evals",
  metrics: "Metrics",
  ml: "ML",
  games: "Games",
  blockchain: "Blockchain",
  sandbox: "Sandbox",
  capabilities: "Agent Capabilities",
  sessions: "Sessions",
  schedules: "Schedules",
  lessons: "Lessons",
  artifacts: "Artifacts",
  crews: "Crews",
  live: "Live",
  settings: "Settings",
};

const AGENT_ID = "companion_x";
interface CopilotChatSidebarProps {
  onToggle: () => void;
  activeView?: CanvasViewId;
  /** Current sidebar width in px (controlled by the workbench layout). */
  width: number;
  /** Called during drag with the requested new width. */
  onResize: (nextWidth: number) => void;
}

export function CopilotChatSidebar({ onToggle, activeView, width, onResize }: CopilotChatSidebarProps) {
  const { entries: live, connected } = useLiveToolStream();
  const headerTool = pickHeaderTool(live);
  const callbacks = useChatCallbacks(AGENT_ID);
  const { preferences } = useChatPreferences();
  const { agent } = useAgent({ agentId: AGENT_ID });
  const pinnedPrompt = preferences.pinLatestPrompt ? latestUserPrompt(agent.messages) : null;
  const turns = useMemo(() => turnsFromMessages(agent.messages), [agent.messages]);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const jumpToTurn = (index: number) => {
    const root = transcriptRef.current;
    if (!root || turns.length < 2) return;
    // Best-effort proportional scroll (row 11's own "proportional rail"
    // model): find the scrollable transcript element and seek to the
    // turn's fractional position — no fragile per-message DOM anchoring.
    const scroller = Array.from(root.querySelectorAll<HTMLElement>("*"))
      .find((el) => el.scrollHeight > el.clientHeight + 8) ?? root;
    scroller.scrollTop = (index / (turns.length - 1)) * (scroller.scrollHeight - scroller.clientHeight);
  };
  const [draft, setDraft] = useState("");
  // Chat right-side-panel (registry-driven; off by default → no regression
  // when closed). Summary is the first real tab (row 18's proper home);
  // future tabs (Pins/Side/Browser/…) append to this array.
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelTab, setPanelTab] = useState("summary");
  // Row 19: opening the Side panel from a `/side`·`/btw` composer command
  // seeds the tab's input with the (prefix-stripped) query.
  const [sideSeed, setSideSeed] = useState<string | undefined>(undefined);
  const openSide = useMemo(() => (query: string) => {
    if (query) setSideSeed(query);
    setPanelTab("side");
    setPanelOpen(true);
    setDraft("");
  }, []);
  const panelTabs: ChatPanelTab[] = useMemo(() => mergeContributedTabs([
    { id: "summary", label: "Summary", render: () => <ChatSummaryTab threadId={agent.threadId} /> },
    { id: "pins", label: "Pins", render: () => <ChatPinsTab threadId={agent.threadId} /> },
    { id: "files", label: "Files", render: () => (
      <ChatFilesTab onInsert={(ref) => setDraft((d) => (d ? `${d} ${ref}` : ref))} />
    ) },
    { id: "side", label: "Side", render: () => <ChatSideTab seed={sideSeed} /> },
    { id: "browser", label: "Browser", render: () => <ChatBrowserTab /> },
  ], []), [agent.threadId, sideSeed]);

  // Memoise the slot components so identity stays stable across renders
  // (otherwise CopilotChatMessageView remounts every assistant on each
  // tick of the live tool stream).
  const AssistantSlot = useMemo(
    () => makeAssistantMessageSlot({
      onThumbsUp: callbacks.onThumbsUp,
      onThumbsDown: callbacks.onThumbsDown,
      onRegenerate: callbacks.onRegenerate,
      onReadAloud: callbacks.onReadAloud,
      onRewind: callbacks.onRewind,
      onPin: callbacks.onPin,
      onShare: callbacks.onShare,
      // bd-ezy3: route fenced-code blocks through our themed
      // syntax-highlighter + copy-button shell. Inline code keeps the
      // default v2 styling.
      markdownRenderer: CodeBlockMarkdownRenderer,
    }),
    [
      callbacks.onThumbsUp, callbacks.onThumbsDown, callbacks.onRegenerate,
      callbacks.onReadAloud, callbacks.onRewind, callbacks.onPin, callbacks.onShare,
    ],
  );
  const UserSlot = useMemo(
    () => makeUserMessageSlot({ onEditMessage: callbacks.onEditMessage }),
    [callbacks.onEditMessage],
  );
  // Row 12 (feature-map): bakes textArea/sendButton overrides into the
  // SAME component this app already used at the `input` slot, since a
  // component-shaped slot value doesn't also receive a sibling props
  // object from the caller (see composer-collapse.tsx's own comment).
  const InputSlot = useMemo(
    () => makeCollapsibleComposerInput(preferences.collapseMessageInput, {
      textArea: McpReadyTextArea, sendButton: StopAwareSendButton,
      disclaimer: ChatDisclaimer, showDisclaimer: true,
    }, openSide),
    [preferences.collapseMessageInput, openSide],
  );

  return (
    <aside
      style={{ width }}
      className="relative flex h-full shrink-0 flex-col border-l border-border/50 bg-card/10 backdrop-blur-md"
    >
      <ChatResizeHandle onResize={onResize} />
      <SteerDeliveryListener agentId={AGENT_ID} />

      {/* Header */}
      <div className="flex h-10 items-center justify-between border-b border-border/50 px-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase shrink-0">Chat</span>
          {activeView && (
            <>
              <span className="text-border/50 shrink-0">·</span>
              <span className="text-[10px] text-muted-foreground/70 truncate">{VIEW_LABELS[activeView]}</span>
            </>
          )}
          {headerTool && (
            <>
              <span className="text-border/50 shrink-0">·</span>
              <span className={cn(
                "h-1.5 w-1.5 rounded-full shrink-0",
                connected ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground/40",
              )} />
              <span
                className="text-[10px] text-muted-foreground/70 truncate max-w-[120px]"
                title={headerTool.entry.title}
              >
                {headerTool.meta.label}
              </span>
            </>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <button onClick={() => setPanelOpen((o) => !o)} aria-label="Toggle side panel"
            aria-pressed={panelOpen}
            className={cn("rounded-md p-1 transition-colors hover:bg-accent/50",
              panelOpen ? "text-violet-400" : "text-muted-foreground hover:text-foreground")}
            title="Summary & panels">
            <PanelRightIcon className="h-4 w-4" />
          </button>
          <button onClick={onToggle}
            className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
            title="Close chat">
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      <SessionDeck agentId={AGENT_ID} />

      {/* Persona '/' palette (bd:python-factory-d4roe.3) — pick a chat
          persona; the next run carries it via forwardedProps. Sits in a
          thin sub-header strip just above the chat surface input area. */}
      <div className="flex h-7 items-center gap-2 border-b border-border/30 px-3">
        <PersonaPalette />
        <span className="text-border/40">·</span>
        <ModelPicker agentId={AGENT_ID} />
      </div>

      <McpConnectionNotice />

      <PinnedPromptBanner prompt={pinnedPrompt} />

      <div ref={transcriptRef} className="relative flex-1 overflow-hidden">
        <TurnMinimap turns={turns} onJump={jumpToTurn} />
        <AskAboutThisOverlay containerRef={transcriptRef}
          onAsk={(text) => openSide(buildAskAboutPrompt(text))} />
        <CopilotChat
          agentId={AGENT_ID}
          className="h-full"
          inputValue={draft}
          onInputChange={setDraft}
          labels={{
            chatInputPlaceholder: "Ask anything…",
            welcomeMessageText: "Hi there — Let's Jam!",
          }}
          // Wire the v2 message-toolbar callbacks via slot components
          // (bd-2dq6). v2 1.53 documents `onThumbsUp` etc as
          // `(message) => void` but binds them as plain `onClick`
          // handlers internally, dropping the message arg. The slot
          // components in feedback-message-slot.tsx wrap the defaults
          // and re-supply the message from each row's render scope.
          //
          // Cast through `as never` because v2's SlotValue<typeof X>
          // statically requires the namespaced sub-components (Toolbar,
          // CopyButton, ...) on the value, which our wrapper FC doesn't
          // expose. The runtime check is `isReactComponentType` which
          // only verifies it's a function — wrapper FCs are valid.
          messageView={{
            assistantMessage: AssistantSlot as never,
            userMessage: UserSlot as never,
            // Cap the reasoning ("Thinking…") panel so it never
            // pushes the response below the fold (bd-k8xk).
            reasoningMessage: ReasoningSlot as never,
            // Group each spawn's messages into one collapsible box
            // (bd:python-factory-esb6n). The children render-prop hands us
            // the already-memoized message elements; SubAgentGroupedView
            // wraps contiguous sub-agent runs in a bordered box and
            // re-emits the cursor + interrupt element.
            children: ({
              messageElements,
              messages,
              isRunning,
              interruptElement,
            }: {
              messageElements: ReactElement[];
              messages: Message[];
              isRunning: boolean;
              interruptElement: ReactElement | null;
            }) => (
              <SubAgentGroupedView
                messageElements={messageElements}
                messages={messages}
                isRunning={isRunning}
                interruptElement={interruptElement}
              />
            ),
          }}
          // Same SDK slot-typing gap as messageView above: the runtime
          // accepts a wrapper FC, the type wants `typeof CopilotChatInput`.
          input={InputSlot as never}
        />
      </div>
      {panelOpen && (
        <div className="absolute right-0 top-10 bottom-0 z-20 w-72 max-w-[70%] shadow-xl">
          <ChatSidePanel tabs={panelTabs} activeId={panelTab}
            onSelect={setPanelTab} onClose={() => setPanelOpen(false)} />
        </div>
      )}
    </aside>
  );
}
