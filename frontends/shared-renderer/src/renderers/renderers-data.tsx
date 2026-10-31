"use client";

import React from "react";
import {
  Card, CardHeader, CardTitle, CardContent,
} from "../ui/card";
import { Badge } from "../ui/badge";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";
import { useToolData } from "./use-tool-data";

/* TableRenderer */

export function TableRenderer({ node }: RendererProps) {
  const { columns = [], rows = [], className } = node.props as {
    columns?: { key: string; label: string }[];
    rows?: Record<string, unknown>[]; className?: string;
  };
  return (
    <div className={cn("w-full overflow-auto", className)}>
      <table className="w-full caption-bottom text-sm">
        <thead className="[&_tr]:border-b">
          <tr className="border-b transition-colors hover:bg-muted/50">
            {columns.map((col) => (
              <th key={col.key} className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_tr:last-child]:border-0">
          {rows.map((row, i) => (
            <tr key={i} className="border-b transition-colors hover:bg-muted/50">
              {columns.map((col) => (
                <td key={col.key} className="p-4 align-middle">{String(row[col.key] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ChartRenderer */

function extractChartData(raw: unknown): Record<string, unknown>[] {
  if (Array.isArray(raw)) return raw;
  if (typeof raw === "object" && raw != null) {
    const obj = raw as Record<string, unknown>;
    for (const key of ["buckets", "data", "result", "items", "series"]) {
      if (Array.isArray(obj[key])) return obj[key] as Record<string, unknown>[];
    }
  }
  return [];
}

export function ChartRenderer({ node }: RendererProps) {
  const {
    data: staticData = [], data_tool, xKey = "name", yKey = "value",
    title, empty_state, className,
  } = node.props as {
    data?: Record<string, unknown>[]; data_tool?: string;
    xKey?: string; yKey?: string; chartType?: string;
    title?: string; empty_state?: string; className?: string;
  };

  const { data: toolResult, loading, error } = useToolData(data_tool);

  // bd:python-factory-lbvkh — defensive: if the agent emits a malformed
  // Chart payload (e.g. ``data: "not-an-array"``) or ``data_tool``
  // extraction returns a non-array shape we don't recognize, render the
  // empty state instead of letting ``.filter`` throw and nuke the whole
  // chat panel through React's error boundary. Combined with the
  // <InlineView> ErrorBoundary added in the same bd, a single bad
  // producer can no longer require a full page reload.
  const rawData = data_tool ? extractChartData(toolResult) : staticData;
  const dataArr = Array.isArray(rawData) ? rawData : [];
  if (!Array.isArray(rawData) && rawData != null) {
    // Soft warn — surface in devtools without crashing the panel.
    // eslint-disable-next-line no-console
    console.warn(
      "[ChartRenderer] expected array data; got",
      typeof rawData,
      "— rendering empty state",
    );
  }
  // Filter out null-value buckets (metrics trend API returns many)
  const data = dataArr.filter((d) => d != null && (d as Record<string, unknown>)[yKey] != null);
  const maxVal = Math.max(1, ...data.map((d) => Number((d as Record<string, unknown>)[yKey] ?? 0)));

  if (loading) {
    return (
      <Card className={className}>
        {title && <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>}
        <CardContent>
          <div className="flex items-end gap-2 h-40 animate-pulse">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex-1 rounded-t bg-muted" style={{ height: `${20 + Math.random() * 60}%` }} />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      {title && <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>}
      <CardContent>
        {error && <p className="text-sm text-destructive mb-2">{error}</p>}
        {data.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty_state ?? "No chart data"}</p>
        ) : (
          <div className="flex items-end gap-2 h-40">
            {data.map((d, i) => {
              const val = Number(d[yKey] ?? 0);
              return (
                <div key={i} className="flex flex-col items-center flex-1 gap-1">
                  <span className="text-xs text-muted-foreground">{val}</span>
                  <div className="w-full rounded-t bg-primary transition-all"
                    style={{ height: `${(val / maxVal) * 100}%` }} />
                  <span className="text-xs text-muted-foreground truncate max-w-full">
                    {String(d[xKey] ?? "")}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ImageRenderer */

export function ImageRenderer({ node }: RendererProps) {
  // bd:python-factory-3hkqx — agent emits arbitrary external/data: URLs
  // (picsum, dicebear, base64, etc.). next/image needs every host
  // pre-configured in next.config.js, so we use a plain <img> here to
  // accept any source the agent produces. Lazy-load + decode async to
  // keep the perf hit minimal. Renderer canary in
  // ``__tests__/renderers-prop-aliases.test.tsx`` pins the contract.
  const { src, alt = "", width = 400, height = 300, className } = node.props as {
    src?: string; alt?: string; width?: number; height?: number; className?: string;
  };
  if (!src) {
    return (
      <div className="flex h-32 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
        No image source
      </div>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      loading="lazy"
      decoding="async"
      className={cn("rounded-md", className)}
    />
  );
}

/* CodeRenderer */

export function CodeRenderer({ node }: RendererProps) {
  const { code = "", language = "", title, className } = node.props as {
    code?: string; language?: string; title?: string; className?: string;
  };
  return (
    <div className={cn("rounded-md border", className)}>
      {(title || language) && (
        <div className="flex items-center justify-between border-b bg-muted px-4 py-2">
          {title && <span className="text-sm font-medium">{title}</span>}
          {language && <Badge variant="secondary">{language}</Badge>}
        </div>
      )}
      <pre className="overflow-auto p-4"><code className="text-sm">{code}</code></pre>
    </div>
  );
}

/* TimelineRenderer */

export function TimelineRenderer({ node }: RendererProps) {
  const { items = [], className } = node.props as {
    items?: { title: string; description?: string; time?: string; status?: string }[];
    className?: string;
  };
  return (
    <div className={cn("relative ml-3 border-l border-border pl-6 space-y-6", className)}>
      {items.map((item, i) => (
        <div key={i} className="relative">
          <div className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-primary bg-background" />
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{item.title}</span>
              {item.status && <Badge variant="outline">{item.status}</Badge>}
            </div>
            {item.description && <p className="text-sm text-muted-foreground">{item.description}</p>}
            {item.time && <p className="text-xs text-muted-foreground">{item.time}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
