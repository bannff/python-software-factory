"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, RefreshCw, AlertCircle } from "lucide-react";
import Link from "next/link";
import { callTool, listTools } from "@/lib/api";
import { ComponentTree, type ReactAdapterNode, unwrapToolResult } from "@companion-x/shared-renderer";
import { Button } from "@/components/ui/button";

function extractNodes(data: unknown): ReactAdapterNode[] {
  if (!data || typeof data !== "object") return [];
  const obj = data as Record<string, unknown>;

  // ReactAdapter envelope: { content: { components: [...] } }
  if (obj.content && typeof obj.content === "object") {
    const content = obj.content as Record<string, unknown>;
    if (Array.isArray(content.components)) {
      return content.components as ReactAdapterNode[];
    }
  }
  // Direct components array
  if (Array.isArray(obj.components)) {
    return obj.components as ReactAdapterNode[];
  }
  // Array of nodes
  if (Array.isArray(data)) return data as ReactAdapterNode[];
  // Single node
  if (obj.id) return [data as ReactAdapterNode];
  return [];
}

async function fetchRawView(viewId: string): Promise<ReactAdapterNode[]> {
  const { tools } = await listTools();
  const viewTools = tools.filter((t) => t.endsWith("_get_views"));
  for (const tool of viewTools) {
    const res = await callTool(tool).catch(() => null);
    const payload = unwrapToolResult(res);
    const viewData = payload && typeof payload === "object" && "views" in payload
      ? (payload as { views: unknown }).views
      : payload;
    const views = Array.isArray(viewData) ? viewData : [viewData];
    const match = views.find(
      (v: Record<string, unknown>) => v.id === viewId,
    );
    if (match) return extractNodes(match);
  }
  return [];
}

export default function ViewDetailPage() {
  const params = useParams<{ id: string }>();
  const viewId = params.id;
  const [nodes, setNodes] = useState<ReactAdapterNode[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchView = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Try ReactAdapter first
      const res = await callTool("ui_render_view", {
        view_id: viewId,
        adapter: "react",
      });
      const result = unwrapToolResult(res) as Record<string, unknown>;
      if (result?.error) throw new Error(result.error as string);
      const extracted = extractNodes(result);
      if (extracted.length > 0) {
        setNodes(extracted);
        return;
      }
      // Fallback: render raw view data
      const raw = await fetchRawView(viewId);
      setNodes(raw);
    } catch {
      // ReactAdapter failed — try raw view data
      try {
        const raw = await fetchRawView(viewId);
        setNodes(raw.length > 0 ? raw : null);
        if (raw.length === 0) setError("View not found");
      } catch (err2) {
        setError(
          err2 instanceof Error ? err2.message : "Failed to render view",
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [viewId]);

  useEffect(() => {
    fetchView();
  }, [fetchView]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Link href="/">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Chat
          </Button>
        </Link>
        <span className="text-sm text-muted-foreground">/ {viewId}</span>
        <Button
          variant="outline"
          size="sm"
          className="ml-auto"
          onClick={fetchView}
          disabled={isLoading}
        >
          <RefreshCw className="mr-1 h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {isLoading && (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-lg border bg-muted"
            />
          ))}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <Button variant="outline" size="sm" onClick={fetchView}>
            Retry
          </Button>
        </div>
      )}

      {!isLoading && !error && nodes && <ComponentTree nodes={nodes} />}
    </div>
  );
}
