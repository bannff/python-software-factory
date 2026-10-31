"use client";

/**
 * GraphBrickView — wraps GraphDetailPanel + BrickViewRenderer.
 * Universal page skeleton: graph (top) + brick item_list (bottom).
 */

import { useState, useCallback } from "react";
import { GraphDetailPanel } from "./graph-detail-panel";
import BrickViewRenderer from "./brick-view-renderer";
import type { CanvasViewId } from "@/lib/types";

interface GraphBrickViewProps {
  /** The brick's *_get_views tool name. */
  viewTool: string;
  /** Default entity type to show in graph when nothing selected. */
  defaultEntityType?: string;
  /** Navigation callback for cross-tab deep links. */
  onNavigate?: (viewId: CanvasViewId) => void;
  /** Height of the graph section. */
  graphHeight?: number;
}

export default function GraphBrickView({
  viewTool,
  defaultEntityType,
  onNavigate,
  graphHeight = 260,
}: GraphBrickViewProps) {
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);

  // Listen for item selection from the BrickViewRenderer
  const handleItemSelect = useCallback((entityId: string) => {
    setSelectedEntityId(entityId);
  }, []);

  return (
    <GraphDetailPanel
      entityId={selectedEntityId}
      entityType={defaultEntityType}
      onNavigate={onNavigate}
      graphHeight={graphHeight}
    >
      <BrickViewRenderer
        viewTool={viewTool}
        onItemSelect={handleItemSelect}
      />
    </GraphDetailPanel>
  );
}
