"use client";

import React from "react";
import { motion } from "framer-motion";
import { LayoutGrid } from "lucide-react";
import { ComponentTree, type ReactAdapterNode } from "@companion-x/shared-renderer";

interface InlineViewProps {
  payload: {
    components?: ReactAdapterNode[];
    name?: string;
    [key: string]: unknown;
  };
}

/**
 * Error boundary for inline A2UI views — bd:python-factory-lbvkh.
 *
 * A single malformed producer payload (e.g. `Chart` with non-array `data`,
 * or any future renderer crash) used to bubble up through React and nuke
 * the entire chat panel ("Application error: client-side exception"). This
 * boundary catches the throw, renders a small destructive-toned card, and
 * resets when the surrounding `payload` changes so the user can recover by
 * sending a new message.
 *
 * Carrier #5 (mcp-ui) will need its own ErrorBoundary similarly when it
 * lands under bd:python-factory-lo1g9.4 — same pattern, different mount.
 */
class InlineViewErrorBoundary extends React.Component<
  { resetKey: unknown; children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidUpdate(prev: { resetKey: unknown }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[InlineView] render failed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          role="alert"
          className="rounded border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
        >
          <p className="font-medium">Inline view failed to render</p>
          <p className="text-xs text-muted-foreground mt-1">
            {this.state.error.message}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export function InlineView({ payload }: InlineViewProps) {
  const components = payload.components;
  if (!components || components.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="ml-11 my-2"
    >
      <div className="rounded-xl border border-border/50 bg-card/50 backdrop-blur-sm overflow-hidden shadow-sm">
        {payload.name && (
          <div className="flex items-center gap-2 border-b border-border/50 px-4 py-2">
            <LayoutGrid className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">
              {payload.name}
            </span>
          </div>
        )}
        <div className="p-4">
          <InlineViewErrorBoundary resetKey={payload}>
            <ComponentTree nodes={components} />
          </InlineViewErrorBoundary>
        </div>
      </div>
    </motion.div>
  );
}
