"use client";

/**
 * <McpUiErrorBoundary> — sibling of `<InlineViewErrorBoundary>` for
 * carrier #5 (bd:python-factory-eyahj, mirrors bd:python-factory-lbvkh).
 *
 * Same shape: catches throws inside the SDK renderer, shows a small
 * destructive card, resets when `resetKey` changes so a new resource
 * paint can recover.
 */

import React from "react";

interface Props {
  resetKey: unknown;
  children: React.ReactNode;
}

interface State {
  error: Error | null;
}

export class McpUiErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props): void {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("[McpUiFrame] render failed:", error, info.componentStack);
  }

  render(): React.ReactNode {
    if (this.state.error) {
      return (
        <div
          data-testid="mcp-ui-error"
          role="alert"
          className="rounded border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
        >
          <p className="font-medium">External UI failed to render</p>
          <p className="text-xs text-muted-foreground mt-1">
            {this.state.error.message}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
