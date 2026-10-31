"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { cn } from "../lib/utils";
import type { RendererProps } from "./renderer-types";
import { SparklineInline, type SparklineProps } from "./renderers-sparkline";
import { useToolData } from "./use-tool-data";
import { MetadataChip, type MetadataChipEntry } from "./renderers-metadata-chip";
import {
  ChartTabContent,
  AlertTabContent,
  ListTabContent,
  type TabSpec,
} from "./renderers-tab-content";

/* ── Types ── */

type MetadataEntry = { label: string; value?: unknown; path?: string; render_as?: string; zone?: "config" | "identity" };

type DetailPanelProps = {
  sparkline?: SparklineProps & { data_path?: string };
  metadata?: MetadataEntry[];
  tabs?: TabSpec[];
  item?: Record<string, unknown>;
  resolveFn?: (obj: Record<string, unknown>, path: string) => unknown;
};

/* ── Tab content dispatcher ── */

function TabContent({ tab }: { tab: TabSpec }) {
  if (tab.render_as === "chart" && tab.chart_props?.chart_type === "line") {
    return <ChartTabContent key={tab.id} tab={tab} />;
  }
  if (tab.render_as === "alert") {
    return <AlertTabContent key={tab.id} tab={tab} />;
  }
  if (tab.render_as === "list") {
    return <ListTabContent key={tab.id} tab={tab} />;
  }
  return <RawJsonTabContent key={tab.id} tab={tab} />;
}

function RawJsonTabContent({ tab }: { tab: TabSpec }) {
  const { data, loading, error } = useToolData(tab.tool, tab.args);
  if (loading) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[10px] text-muted-foreground/75">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading
      </span>
    );
  }
  if (error) return <span className="text-[10px] text-destructive">{error}</span>;
  return (
    <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

/* ── DetailPanel ── */

export function DetailPanelInline({ sparkline, metadata, tabs, item, resolveFn }: DetailPanelProps) {
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const resolve = resolveFn ?? ((_o: Record<string, unknown>, p: string) => p);
  const activeTabSpec = tabs?.find((tab) => tab.id === activeTab) ?? null;

  const sparkData =
    sparkline?.data ??
    (sparkline?.data_path && item ? (resolve(item, sparkline.data_path) as number[]) : undefined);

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="overflow-hidden"
    >
      <div className="px-3 pb-2 pt-1 space-y-2">
        {sparkline && (
          Array.isArray(sparkData) && sparkData.length > 0 ? (
            <SparklineInline
              data={sparkData}
              variant={sparkline?.variant}
              color={sparkline?.color}
              height={sparkline?.height}
              max_points={sparkline?.max_points}
            />
          ) : (
            <p className="text-[10px] text-muted-foreground italic">No data yet</p>
          )
        )}

        {metadata && metadata.length > 0 && (() => {
          const entries = metadata.map((m) => ({
            ...m,
            _val: m.value ?? (m.path && item ? resolve(item, m.path) : undefined),
          })).filter((m) => m._val != null);
          const config = entries.filter((m) => m.zone === "config" || (!m.zone && ["Model", "System Prompt", "Judges"].includes(m.label)));
          const identity = entries.filter((m) => m.zone === "identity" || (!m.zone && !["Model", "System Prompt", "Judges"].includes(m.label)));
          const hasZones = config.length > 0 && identity.length > 0;
          return (
            <div className={cn("flex gap-3 text-[11px] border-t border-border/30 pt-2", hasZones && "justify-between")}>
              <div className="flex flex-wrap gap-x-3 gap-y-1 min-w-0">
                {(hasZones ? config : entries).map((m) => (
                  <MetadataChip key={m.label} entry={m as MetadataChipEntry} val={m._val} />
                ))}
              </div>
              {hasZones && identity.length > 0 && (
                <div className="flex flex-wrap gap-x-3 gap-y-1 shrink-0 pl-3 border-l border-border/30">
                  {identity.map((m) => (
                    <MetadataChip key={m.label} entry={m as MetadataChipEntry} val={m._val} />
                  ))}
                </div>
              )}
            </div>
          );
        })()}

        {tabs && tabs.length > 0 && (
          <div className="space-y-1">
            <div className="flex gap-1">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(activeTab === t.id ? null : t.id)}
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors",
                    activeTab === t.id
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {activeTabSpec?.tool && (
              <TabContent key={activeTabSpec.id} tab={activeTabSpec} />
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

export function DetailPanelRenderer({ node }: RendererProps) {
  const p = node.props as DetailPanelProps;
  return <DetailPanelInline {...p} />;
}
