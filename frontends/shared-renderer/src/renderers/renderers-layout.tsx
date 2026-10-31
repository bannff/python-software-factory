"use client";

import React, { useState } from "react";
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
} from "../ui/card";
import { Button } from "../ui/button";
import { cn } from "../lib/utils";
import { ViewIcon } from "./renderers-icon";
import type { ReactAdapterNode, RendererProps } from "./renderer-types";

/* DialogRenderer */

export function DialogRenderer({ node, renderChildren }: RendererProps) {
  const { title, description, open: initialOpen = false, className } = node.props as {
    title?: string; description?: string; open?: boolean; className?: string;
  };
  const [open, setOpen] = useState(initialOpen);
  if (!open) {
    return <Button variant="outline" onClick={() => setOpen(true)}>{title ?? "Open Dialog"}</Button>;
  }
  return (
    <>
      <div className="fixed inset-0 z-50 bg-black/80" onClick={() => setOpen(false)} />
      <div className={cn(
        "fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-background p-6 shadow-lg",
        className
      )}>
        {title && <h2 className="text-lg font-semibold">{title}</h2>}
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        <div className="mt-4">{renderChildren(node.children)}</div>
        <button onClick={() => setOpen(false)}
          className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100" aria-label="Close">✕</button>
      </div>
    </>
  );
}

/* ToastRenderer */

export function ToastRenderer({ node }: RendererProps) {
  const { message, variant = "default", duration = 4000 } = node.props as {
    message?: string; variant?: string; duration?: number;
  };
  const [visible, setVisible] = useState(true);
  React.useEffect(() => {
    const timer = setTimeout(() => setVisible(false), duration);
    return () => clearTimeout(timer);
  }, [duration]);
  if (!visible) return null;
  return (
    <div className={cn(
      "fixed bottom-4 right-4 z-50 rounded-md border bg-background px-6 py-4 shadow-lg transition-all",
      variant === "destructive" && "border-destructive text-destructive"
    )}>
      <p className="text-sm">{message ?? "Notification"}</p>
    </div>
  );
}

/* PageRenderer — 3-zone layout */

export function PageRenderer({ node, renderChildren }: RendererProps) {
  const { title, subtitle, icon, gradient = "from-blue-500 to-indigo-600", tooltip, className } =
    node.props as { title?: string; subtitle?: string; icon?: string; gradient?: string; tooltip?: string; className?: string; };
  const children = node.children ?? [];
  const infoChildren = children.filter((c) => c.props.zone === "info");
  const controlChildren = children.filter((c) => c.props.zone === "controls");
  const outputChildren = children.filter(
    (c) => !c.props.zone || (c.props.zone !== "info" && c.props.zone !== "controls"),
  );
  return (
    <div className={cn("space-y-6", className)}>
      <div className={cn("rounded-lg bg-gradient-to-r p-6 text-white", gradient)} title={tooltip}>
        <div className="flex items-center gap-3">
          {/* bd:python-factory-3jcls.1 — route through ViewIcon so a
              kebab-case token resolves to a glyph instead of printing. */}
          <ViewIcon name={icon} className="h-7 w-7" textClassName="text-3xl" />
          <div>
            {title && <h1 className="text-2xl font-bold">{title}</h1>}
            {subtitle && <p className="mt-1 text-white/80">{subtitle}</p>}
          </div>
        </div>
      </div>
      {(infoChildren.length > 0 || controlChildren.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {renderChildren(infoChildren)}
          {controlChildren.length > 0 && <div className="lg:col-span-4">{renderChildren(controlChildren)}</div>}
        </div>
      )}
      {outputChildren.length > 0 && <div className="space-y-4">{renderChildren(outputChildren)}</div>}
    </div>
  );
}

/* TreeRenderer */

type TreeNode = { label: string; children?: TreeNode[] };

function TreeItem({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = (node.children?.length ?? 0) > 0;
  return (
    <div style={{ paddingLeft: depth > 0 ? 16 : 0 }}>
      <button onClick={() => hasChildren && setExpanded(!expanded)} className={cn(
        "flex items-center gap-1.5 py-1 text-sm hover:text-foreground",
        hasChildren ? "text-foreground cursor-pointer" : "text-muted-foreground cursor-default"
      )}>
        {hasChildren && <span className="text-xs">{expanded ? "▼" : "▶"}</span>}
        {!hasChildren && <span className="text-xs ml-3">•</span>}
        {node.label}
      </button>
      {expanded && node.children?.map((child, i) => <TreeItem key={i} node={child} depth={depth + 1} />)}
    </div>
  );
}

export function TreeRenderer({ node }: RendererProps) {
  const { nodes = [], className } = node.props as { nodes?: TreeNode[]; className?: string };
  return (
    <div className={cn("rounded-md border p-3", className)}>
      {nodes.map((n, i) => <TreeItem key={i} node={n} />)}
    </div>
  );
}

/* SpacerRenderer / DividerRenderer (bd:python-factory-3hkqx round 3 —
   meta-architect verdict cec79d55, fills missing PascalCase renderers) */

export function SpacerRenderer({ node }: RendererProps) {
  const { height, size, width } = node.props as {
    height?: number | string; size?: number | string; width?: number | string;
  };
  const h = height ?? size ?? 16;
  const w = width;
  return (
    <div
      aria-hidden="true"
      style={{ height: typeof h === "number" ? `${h}px` : h,
               width: w !== undefined ? (typeof w === "number" ? `${w}px` : w) : undefined }}
    />
  );
}

export function DividerRenderer({ node }: RendererProps) {
  const { orientation = "horizontal", className } = node.props as {
    orientation?: "horizontal" | "vertical"; className?: string;
  };
  return (
    <div
      role="separator"
      aria-orientation={orientation}
      className={cn(
        orientation === "vertical" ? "mx-2 h-full w-px bg-border" : "my-3 h-px w-full bg-border",
        className,
      )}
    />
  );
}

/* CustomRenderer */

export function CustomRenderer({ node, renderChildren }: RendererProps) {
  const { className, ...rest } = node.props as Record<string, unknown> & { className?: string };
  return (
    <Card className={cn("border-dashed", className)}>
      <CardHeader>
        <CardTitle className="text-base">Custom: {node.originalType}</CardTitle>
        <CardDescription>Unhandled component type</CardDescription>
      </CardHeader>
      <CardContent>
        <pre className="text-xs overflow-auto max-h-40">{JSON.stringify(rest, null, 2)}</pre>
        {renderChildren(node.children)}
      </CardContent>
    </Card>
  );
}

/* FallbackComponent */

export function FallbackComponent({ node }: RendererProps) {
  return (
    <div className="rounded-md border border-dashed border-yellow-500/50 bg-yellow-50/50 p-4 dark:bg-yellow-950/20">
      <p className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
        Unknown component: <code>{node.component}</code>
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Original type: {node.originalType} | ID: {node.id}
      </p>
    </div>
  );
}
