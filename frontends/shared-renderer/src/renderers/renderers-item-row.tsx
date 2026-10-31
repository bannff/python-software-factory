"use client";

import React from "react";
import { AnimatePresence } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { cn } from "../lib/utils";
import { StatusDotInline } from "./renderers-status";
import { TrendBadgeInline } from "./renderers-status";
import { DetailPanelInline } from "./renderers-detail-panel";
import { ViewIcon } from "./renderers-icon";
import { resolve, resolveStr, resolveNum, type ItemLayoutSpec, type DetailSpec, BADGE_COLORS } from "./renderers-item-list-utils";

/**
 * bd:python-factory-3jcls.1 — previously fell back to printing the raw
 * token (`cpu-chip`) when it wasn't in ICON_MAP. ``ViewIcon`` renders a
 * glyph, a pictograph, or nothing — never an internal identifier.
 */
function SubtitleIcon({ name }: { name?: string }) {
  return <ViewIcon name={name} className="h-3 w-3 text-muted-foreground" textClassName="text-[10px]" />;
}

export function ItemRow({ item, itemKey, layout, detail, badgeColorMap, isExpanded, onToggle }: {
  item: Record<string, unknown>;
  itemKey: string;
  layout?: ItemLayoutSpec;
  detail?: DetailSpec;
  badgeColorMap: Record<string, string>;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  // Status dot
  const dotValue = resolveNum(item, layout?.status_dot?.value_path);
  const dotState = layout?.status_dot?.states
    ? resolveStr(item, layout.status_dot.value_path) ?? undefined
    : undefined;
  const dotThresholds = layout?.status_dot?.thresholds
    ? { warning: resolveNum(item, layout.status_dot.thresholds.warning), critical: resolveNum(item, layout.status_dot.thresholds.critical) }
    : undefined;

  // Title + subtitle + subtitle icon
  const title = resolveStr(item, layout?.title) ?? itemKey;
  const subtitle = resolveStr(item, layout?.subtitle);
  const subtitleIcon = resolveStr(item, layout?.subtitle_icon);

  // Badge
  const badgeField = layout?.badge?.field;
  const badgeRaw = badgeField
    ? (badgeField.startsWith("$.") ? resolve(item, badgeField) : item[badgeField])
    : undefined;
  const badgeValue = badgeRaw != null && String(badgeRaw).trim() !== ""
    ? String(badgeRaw)
    : undefined;
  const badgeColor = badgeValue ? (badgeColorMap[badgeValue] ?? "gray") : "gray";
  const badgeSuffix = layout?.badge?.suffix ?? "";

  // Value + trend
  const rawValue = layout?.value?.path ? resolve(item, layout.value.path) : undefined;
  const valueFormat = layout?.value?.format;
  const displayValue = rawValue != null
    ? valueFormat === "percent" && typeof rawValue === "number"
      ? `${Math.round(rawValue * 100)}%`
      : String(rawValue)
    : null;
  const trendDir = resolveStr(item, layout?.trend?.direction);
  const trendPct = resolveNum(item, layout?.trend?.change_pct);

  // Detail tabs with resolved args
  const resolvedTabs = detail?.tabs?.map((tab) => {
    if (!tab.args) return tab;
    const resolved: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(tab.args)) {
      resolved[k] = resolve(item, v);
    }
    return { ...tab, args: resolved };
  });

  return (
    <div>
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 rounded-lg border border-border/50 bg-card/30 px-3 py-2.5 text-left hover:bg-accent/20 transition-colors"
      >
        <StatusDotInline value={dotValue} thresholds={dotThresholds} state={dotState} states={layout?.status_dot?.states} />
        <span className="flex-1 min-w-0 flex items-center gap-2">
          <span className="text-sm font-medium truncate">{title}</span>
          {subtitle && <span className="text-[10px] text-muted-foreground/60 truncate shrink-0">{subtitle}</span>}
          <SubtitleIcon name={subtitleIcon} />
          {badgeValue && (
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", BADGE_COLORS[badgeColor] ?? BADGE_COLORS.gray)}>
              {badgeValue}{badgeSuffix}
            </span>
          )}
        </span>
        {displayValue != null ? (
          <span className="flex items-center gap-1.5 shrink-0">
            <span className="text-sm font-semibold">{displayValue}</span>
            {trendDir && <TrendBadgeInline direction={trendDir} change_pct={trendPct} positive_is_good={layout?.trend?.positive_is_good} />}
          </span>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        )}
        <ChevronRight className={cn("h-3.5 w-3.5 text-muted-foreground transition-transform shrink-0", isExpanded && "rotate-90")} />
      </button>
      <AnimatePresence>
        {isExpanded && detail && (
          <DetailPanelInline
            sparkline={detail.sparkline}
            metadata={detail.metadata}
            tabs={resolvedTabs}
            item={item}
            resolveFn={resolve}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
