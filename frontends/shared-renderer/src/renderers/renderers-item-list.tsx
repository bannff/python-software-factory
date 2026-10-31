"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { useBridge } from "../bridge-adapter-context";
import type { RendererProps } from "./renderer-types";
import { useToolData } from "./use-tool-data";
import { FilterBarInline } from "./renderers-filter-bar";
import { ItemRow } from "./renderers-item-row";
import { ViewIcon, resolveIcon, isPictograph } from "./renderers-icon";
import { resolve, extractArray, type ItemListProps } from "./renderers-item-list-utils";

/* ── Subtitle icon (header) ── */

function HeaderIcon({ name }: { name?: string }) {
  return <ViewIcon name={name} className="h-4 w-4 text-indigo-500" />;
}

/* ── Empty state ── */

function EmptyState({ icon, message }: { icon?: string; message?: string }) {
  const hasIcon = Boolean(icon && (resolveIcon(icon) || isPictograph(icon)));
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex h-full flex-col items-center justify-center gap-3 text-center">
      {hasIcon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/10">
          <ViewIcon name={icon} className="h-6 w-6 text-indigo-500/50" textClassName="text-xl" />
        </div>
      )}
      <p className="max-w-lg text-sm text-muted-foreground">{message ?? "No items found."}</p>
    </motion.div>
  );
}

/* ── Main component ── */

export function ItemListRenderer({ node }: RendererProps) {
  const p = node.props as ItemListProps;
  const { data_tool, data_path, item_key = "id", filters, item_layout, detail } = p;
  const bridge = useBridge();

  const { data: rawData, loading, error } = useToolData(data_tool, {}, { refreshMs: p.refresh_ms });
  const items = useMemo(() => extractArray(rawData, data_path), [rawData, data_path]);

  const { data: statsRaw } = useToolData(p.header?.stats_tool, {}, { refreshMs: p.refresh_ms });

  // Snapshot enrichment
  const [snapshots, setSnapshots] = useState<Record<string, Record<string, unknown>>>({});
  const snapshotFetched = useRef(false);

  useEffect(() => {
    if (!p.item_snapshot_tool || items.length === 0 || snapshotFetched.current) return;
    snapshotFetched.current = true;
    const map: Record<string, Record<string, unknown>> = {};
    const fetches = items.map((item) => {
      const args: Record<string, unknown> = {};
      if (p.item_snapshot_args) {
        for (const [k, v] of Object.entries(p.item_snapshot_args)) {
          args[k] = resolve(item, v);
        }
      }
      const key = String(item[item_key] ?? "");
      return bridge.callTool(p.item_snapshot_tool!, args)
        .then((r) => { map[key] = ((r as unknown as Record<string, unknown>).result ?? r) as Record<string, unknown>; })
        .catch(() => {});
    });
    Promise.all(fetches).then(() => setSnapshots({ ...map }));
  }, [items, p.item_snapshot_tool, p.item_snapshot_args, item_key, bridge]);

  const enrichedItems = useMemo(() => {
    if (!p.snapshot_merge_path || Object.keys(snapshots).length === 0) return items;
    return items.map((item) => {
      const key = String(item[item_key] ?? "");
      const snap = snapshots[key];
      return snap ? { ...item, [p.snapshot_merge_path!]: snap } : item;
    });
  }, [items, snapshots, p.snapshot_merge_path, item_key]);

  // Filter
  const [filterValue, setFilterValue] = useState<string | null>(null);
  const filtered = useMemo(() => {
    if (!filterValue || !filters?.field) return enrichedItems;
    return enrichedItems.filter((item) => item[filters.field!] === filterValue);
  }, [enrichedItems, filterValue, filters?.field]);

  const filterCounts = useMemo(() => {
    if (!filters?.field || !filters.show_counts) return undefined;
    const counts: Record<string, number> = {};
    for (const item of enrichedItems) {
      const v = String(item[filters.field!] ?? "");
      counts[v] = (counts[v] ?? 0) + 1;
    }
    return counts;
  }, [enrichedItems, filters?.field, filters?.show_counts]);

  const [expandedId, setExpandedId] = useState<string | null>(null);

  const emptyMessage = useMemo(() => {
    if (enrichedItems.length > 0 && filterValue) {
      return `No runs match ${filterValue}.`;
    }
    return p.empty_message;
  }, [enrichedItems.length, filterValue, p.empty_message]);

  const statsText = useMemo(() => {
    if (!p.header?.stats_map || !statsRaw) return "";
    const parts: string[] = [];
    for (const [label, path] of Object.entries(p.header.stats_map)) {
      const v = resolve(statsRaw as Record<string, unknown>, path);
      if (v != null) parts.push(`${v} ${label}`);
    }
    return parts.join(" · ");
  }, [statsRaw, p.header?.stats_map]);

  const badgeColorMap = useMemo(() => {
    if (!item_layout?.badge?.color_map) return filters?.colors ?? {};
    if (item_layout.badge.color_map === "filters.colors") return filters?.colors ?? {};
    return {};
  }, [item_layout?.badge?.color_map, filters?.colors]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border/50 bg-card/10 px-4 py-2">
        <HeaderIcon name={p.header?.icon} />
        {statsText && <span className="text-xs font-medium text-muted-foreground">{statsText}</span>}
        {filters && (
          <div className="ml-auto max-w-full">
            <FilterBarInline values={filters.values} colors={filters.colors} show_counts={filters.show_counts} counts={filterCounts} onFilter={setFilterValue} />
          </div>
        )}
      </div>
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex h-full items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
        ) : error ? (
          <p className="text-sm text-destructive text-center py-8">{error}</p>
        ) : filtered.length > 0 ? (
          <div className="space-y-2">
            {filtered.map((item) => {
              const key = String(item[item_key] ?? "");
              const isExpanded = expandedId === key;
              return <ItemRow key={key} item={item} itemKey={key} layout={item_layout} detail={detail} badgeColorMap={badgeColorMap} isExpanded={isExpanded} onToggle={() => setExpandedId(isExpanded ? null : key)} />;
            })}
          </div>
        ) : (
          <EmptyState icon={p.empty_icon} message={emptyMessage} />
        )}
      </div>
    </div>
  );
}
