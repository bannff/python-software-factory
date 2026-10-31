"use client";

import { useEffect, useMemo } from "react";
import { AlertCircle, Inbox } from "lucide-react";
import { useToolData, ComponentTree, type ReactAdapterNode } from "@companion-x/shared-renderer";
import { useWorkbenchContext } from "@/lib/workbench-context";
import { resolveBrickViewId } from "@/lib/brick-view-state";

interface BrickViewDef {
  id: string;
  name: string;
  brick?: string;
  components: BrickNode[];
  metadata?: { description?: string };
}

interface BrickNode {
  id: string;
  type: string;
  props?: Record<string, unknown>;
  children?: BrickNode[];
}

function normalizeNodes(nodes: BrickNode[]): ReactAdapterNode[] {
  return nodes.map((node) => ({
    id: node.id,
    component: node.type,
    originalType: node.type,
    props: node.props ?? {},
    children: node.children ? normalizeNodes(node.children) : undefined,
  }));
}

interface BrickViewRendererProps {
  viewTool: string;
  viewIndex?: number;
  onItemSelect?: (entityId: string) => void;
}

export default function BrickViewRenderer({
  viewTool, viewIndex = 0, onItemSelect,
}: BrickViewRendererProps) {
  const { data, loading, error } = useToolData(viewTool);
  const workbench = useWorkbenchContext();

  const viewState = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return null;
    const views = data as BrickViewDef[];
    const brick = views[0]?.brick ?? viewTool;
    const metadata = views.map((view) => ({
      id: view.id, name: view.name, description: view.metadata?.description,
    }));
    const activeId = resolveBrickViewId(
      metadata, workbench.selectedBrickViews[brick], viewIndex,
    );
    const activeView = views.find((view) => view.id === activeId) ?? views[0];
    if (!activeView?.components?.length) return null;
    return { views, metadata, brick, activeId: activeView.id, nodes: normalizeNodes(activeView.components) };
  }, [data, viewIndex, viewTool, workbench.selectedBrickViews]);

  useEffect(() => {
    if (viewState) {
      workbench.registerBrickViews(viewState.brick, viewState.metadata, viewIndex);
    }
  }, [viewState?.brick, viewState?.metadata, viewIndex, workbench.registerBrickViews]);

  const gatewayError = useMemo(() => {
    if (data && typeof data === "object" && !Array.isArray(data)) {
      const message = (data as Record<string, unknown>).error;
      return typeof message === "string" ? message : null;
    }
    return null;
  }, [data]);

  if (loading && !data) {
    return (
      <div className="grid gap-3 p-4 sm:grid-cols-3" aria-label="Loading brick views">
        {[0, 1, 2].map((key) => <div key={key} className="h-24 animate-pulse rounded-lg border bg-muted/40" />)}
      </div>
    );
  }
  if ((error || gatewayError) && !viewState) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
        <AlertCircle className="h-5 w-5 text-destructive/60" />
        <p className="max-w-sm text-sm text-muted-foreground">{error || gatewayError}</p>
      </div>
    );
  }
  if (!viewState) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <Inbox className="h-5 w-5 text-muted-foreground/50" />
        <p className="text-sm text-muted-foreground">No view data available.</p>
      </div>
    );
  }

  const tree = <ComponentTree nodes={viewState.nodes} onItemSelect={onItemSelect} />;
  if (viewState.views.length === 1) return tree;
  return (
    <div className="flex h-full min-h-0 flex-col">
      <nav className="flex shrink-0 gap-1 overflow-x-auto border-b px-4 py-2" aria-label="Brick views">
        {viewState.metadata.map((view) => (
          <button
            key={view.id}
            type="button"
            title={view.description}
            aria-pressed={view.id === viewState.activeId}
            onClick={() => workbench.selectBrickView(viewState.brick, view.id)}
            className={view.id === viewState.activeId
              ? "rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
              : "rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted"}
          >
            {view.name}
          </button>
        ))}
      </nav>
      <div className="min-h-0 flex-1 overflow-auto">{tree}</div>
    </div>
  );
}
