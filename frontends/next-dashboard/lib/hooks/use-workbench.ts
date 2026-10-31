"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useRunFocus } from "@/lib/hooks/use-run-focus";
import {
  type ViewHistory, initHistory, pushView, stepBack, stepForward,
  canBack, canForward, currentView,
} from "@/lib/view-history";
import type {
  CanvasViewId, CanvasTab, NavigationRef, NavigationSurface,
} from "@/lib/types";
import {
  normalizeBrickViews,
  resolveBrickViewId,
  type BrickViewMetadata,
} from "@/lib/brick-view-state";

const DEFAULT_TAB: CanvasTab = {
  id: "welcome", viewId: "welcome", label: "Welcome", closable: false,
};

const VIEW_LABELS: Record<CanvasViewId, string> = {
  welcome: "Welcome", graph: "Graph", "timeline-v2": "Timeline",
  findings: "Findings", evals: "Evals", metrics: "Metrics", ml: "ML",
  games: "Games", blockchain: "Blockchain", sandbox: "Sandbox",
  capabilities: "Agent Capabilities", sessions: "Sessions", schedules: "Schedules", lessons: "Lessons",
  artifacts: "Artifacts", crews: "Crews", live: "Live", settings: "Settings",
};

const SURFACE_VIEWS: Partial<Record<NavigationSurface, CanvasViewId>> = {
  graph: "graph", timeline: "timeline-v2", evals: "evals", metrics: "metrics",
};

function snapshotNavigationRef(ref: NavigationRef): NavigationRef {
  const graphContext = ref.graph_context
    ? Object.freeze({ ...ref.graph_context }) : null;
  const focusOrigin = ref.focus_origin
    ? Object.freeze({ ...ref.focus_origin }) : ref.focus_origin;
  return Object.freeze({
    ...ref, graph_context: graphContext, focus_origin: focusOrigin,
  }) as NavigationRef;
}

export function useWorkbench() {
  const [activeView, setActiveView] = useState<CanvasViewId>("welcome");
  // Row 28: Back/Forward over view history. ``pushView`` records forward
  // navigations (in openTab); Back/Forward set the cursor and a pending
  // target that the sync effect drives through ``switchView`` with pushes
  // suppressed, so the history isn't corrupted by its own replay.
  const [viewHistory, setViewHistory] = useState<ViewHistory>(() => initHistory("welcome"));
  const suppressHistory = useRef(false);
  const pendingHistoryNav = useRef<CanvasViewId | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [tabs, setTabs] = useState<CanvasTab[]>([DEFAULT_TAB]);
  const [activeTabId, setActiveTabId] = useState("welcome");
  const [brickViews, setBrickViews] = useState<Record<string, BrickViewMetadata[]>>({});
  const [selectedBrickViews, setSelectedBrickViews] = useState<Record<string, string>>({});
  const [navigationRef, setNavigationRef] = useState<NavigationRef | null>(null);
  const [graphRestoreRequest, setGraphRestoreRequest] = useState<NavigationRef | null>(null);
  const [navigationStatus, setNavigationStatus] = useState(
    "No cross-surface navigation is active.",
  );
  const { focusedRunId, focusRun, clearRunFocus } = useRunFocus();

  const toggleChat = useCallback(() => setChatOpen((p) => !p), []);
  const toggleTerminal = useCallback(() => setTerminalOpen((open) => !open), []);
    useEffect(() => {
    if (new URLSearchParams(window.location.search).get("terminal") === "1") {
      setTerminalOpen(true);
    }
  }, []);

  const openTab = useCallback((viewId: CanvasViewId, label: string) => {
    const safeLabel = label || viewId;
    setTabs((prev) => {
      const existing = prev.find((t) => t.viewId === viewId);
      if (existing) {
        setActiveTabId(existing.id);
        return prev;
      }
      const tab: CanvasTab = { id: viewId, viewId, label: safeLabel, closable: true };
      setActiveTabId(tab.id);
      return [...prev, tab];
    });
    setActiveView(viewId);
    if (!suppressHistory.current) setViewHistory((h) => pushView(h, viewId));
  }, []);

  const closeTab = useCallback((tabId: string) => {
    setTabs((prev) => {
      const filtered = prev.filter((t) => t.id !== tabId || !t.closable);
      if (tabId === activeTabId && filtered.length > 0) {
        const last = filtered[filtered.length - 1];
        setActiveTabId(last.id);
        setActiveView(last.viewId);
      }
      return filtered;
    });
  }, [activeTabId]);

  const switchView = useCallback((viewId: CanvasViewId) => {
    openTab(viewId, VIEW_LABELS[viewId]);
  }, [openTab]);

  const historyBack = useCallback(() => {
    setViewHistory((h) => {
      if (!canBack(h)) return h;
      const next = stepBack(h);
      pendingHistoryNav.current = currentView(next);
      return next;
    });
  }, []);
  const historyForward = useCallback(() => {
    setViewHistory((h) => {
      if (!canForward(h)) return h;
      const next = stepForward(h);
      pendingHistoryNav.current = currentView(next);
      return next;
    });
  }, []);
  // Drive the view for a Back/Forward replay through switchView with the
  // push suppressed, so replaying history never records new entries.
  useEffect(() => {
    const target = pendingHistoryNav.current;
    if (target === null) return;
    pendingHistoryNav.current = null;
    suppressHistory.current = true;
    switchView(target);
    suppressHistory.current = false;
  }, [viewHistory, switchView]);

  const openMetrics = useCallback((ref: NavigationRef) => {
    const snapshot = snapshotNavigationRef(ref);
    setNavigationRef(snapshot);
    setGraphRestoreRequest(null);
    openTab("metrics", VIEW_LABELS.metrics);
    setNavigationStatus(`Opened Metrics for ${snapshot.label}.`);
  }, [openTab]);

  const returnFromMetrics = useCallback((): boolean => {
    if (!navigationRef) {
      setNavigationStatus("Return unavailable: no originating navigation reference.");
      return false;
    }
    const targetView = SURFACE_VIEWS[navigationRef.surface];
    if (!targetView || targetView === "metrics") {
      setNavigationStatus(
        `Return unavailable: the ${navigationRef.surface} surface is not mounted in this workbench.`,
      );
      return false;
    }
    const snapshot = snapshotNavigationRef(navigationRef);
    setNavigationRef(snapshot);
    if (targetView === "graph") setGraphRestoreRequest(snapshot);
    openTab(targetView, VIEW_LABELS[targetView]);
    setNavigationStatus(`Returned to ${snapshot.label}.`);
    return true;
  }, [navigationRef, openTab]);

  const openRelatedGraph = useCallback((): boolean => {
    if (!navigationRef?.graph_selected_ref || !navigationRef.graph_context) {
      setNavigationStatus(
        "Open related graph unavailable: no bounded Graph context was provided.",
      );
      return false;
    }
    const snapshot = snapshotNavigationRef(navigationRef);
    setNavigationRef(snapshot);
    setGraphRestoreRequest(snapshot);
    openTab("graph", VIEW_LABELS.graph);
    setNavigationStatus(`Opened related Graph for ${snapshot.label}.`);
    return true;
  }, [navigationRef, openTab]);

  const acknowledgeGraphRestore = useCallback((targetRef?: string, status?: string) => {
    if (status) setNavigationStatus(status);
    setGraphRestoreRequest((pending) => (
      !targetRef || pending?.graph_selected_ref === targetRef ? null : pending
    ));
  }, []);

  const reportNavigationStatus = useCallback((status: string) => {
    setNavigationStatus(status);
  }, []);

  const navigationAvailability = useMemo(() => {
    const returnView = navigationRef ? SURFACE_VIEWS[navigationRef.surface] : undefined;
    return {
      canReturn: Boolean(returnView && returnView !== "metrics"),
      returnDisabledReason: !navigationRef
        ? "Return unavailable: no originating navigation reference."
        : !returnView || returnView === "metrics"
          ? `Return unavailable: the ${navigationRef.surface} surface is not mounted in this workbench.`
          : "",
      canOpenRelatedGraph: Boolean(
        navigationRef?.graph_selected_ref && navigationRef.graph_context,
      ),
      relatedGraphDisabledReason: "Open related graph unavailable: no bounded Graph context was provided.",
    };
  }, [navigationRef]);

  const registerBrickViews = useCallback((
    brick: string, views: BrickViewMetadata[], fallbackIndex = 0,
  ) => {
    const normalized = normalizeBrickViews(views);
    setBrickViews((prev) => ({ ...prev, [brick]: normalized }));
    setSelectedBrickViews((prev) => {
      const resolved = resolveBrickViewId(normalized, prev[brick], fallbackIndex);
      if (!resolved || prev[brick] === resolved) return prev;
      return { ...prev, [brick]: resolved };
    });
  }, []);

  const selectBrickView = useCallback((brick: string, viewId: string): boolean => {
    if (!brickViews[brick]?.some((view) => view.id === viewId)) return false;
    setSelectedBrickViews((prev) => ({ ...prev, [brick]: viewId }));
    return true;
  }, [brickViews]);

  return {
    activeView, chatOpen, terminalOpen, tabs, activeTabId, brickViews, selectedBrickViews,
    navigationRef, graphRestoreRequest, navigationStatus,
    focusedRunId, focusRun, clearRunFocus,
    ...navigationAvailability,
    toggleChat, toggleTerminal, switchView, openTab, closeTab, registerBrickViews, selectBrickView,
    historyBack, historyForward,
    canHistoryBack: canBack(viewHistory), canHistoryForward: canForward(viewHistory),
    openMetrics, returnFromMetrics, openRelatedGraph, acknowledgeGraphRestore,
    reportNavigationStatus,
    setActiveTabId: useCallback((id: string) => {
      setActiveTabId(id);
      const tab = tabs.find((t) => t.id === id);
      if (tab) setActiveView(tab.viewId);
    }, [tabs]),
  };
}
