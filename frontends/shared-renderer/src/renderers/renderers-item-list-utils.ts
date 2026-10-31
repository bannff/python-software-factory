/* Shared types and utilities for item_list frame components. */

import type { FilterBarProps } from "./renderers-filter-bar";

/* ── JSONPath-lite resolver ── */

export function resolve(obj: Record<string, unknown>, path: unknown): unknown {
  if (typeof path !== "string" || !path.startsWith("$.")) return path;
  const keys = path.slice(2).split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

export function resolveStr(obj: Record<string, unknown>, path?: string): string | undefined {
  if (!path) return undefined;
  const v = resolve(obj, path);
  return v != null ? String(v) : undefined;
}

export function resolveNum(obj: Record<string, unknown>, path?: string): number | undefined {
  if (!path) return undefined;
  const v = resolve(obj, path);
  return typeof v === "number" ? v : undefined;
}

/* ── Badge color map ── */

export const BADGE_COLORS: Record<string, string> = {
  blue: "bg-blue-500/10 text-blue-400",
  orange: "bg-orange-500/10 text-orange-400",
  emerald: "bg-emerald-500/10 text-emerald-400",
  purple: "bg-purple-500/10 text-purple-400",
  red: "bg-red-500/10 text-red-400",
  yellow: "bg-yellow-500/10 text-yellow-400",
  gray: "bg-gray-500/10 text-gray-400",
};

/* ── Shared types ── */

export type ItemLayoutSpec = {
  status_dot?: { value_path?: string; thresholds?: Record<string, string>; states?: Record<string, string> };
  title?: string;
  subtitle?: string;
  subtitle_icon?: string;
  badge?: { field?: string; color_map?: string; suffix?: string };
  value?: { path?: string; format?: string };
  trend?: { direction?: string; change_pct?: string; positive_is_good?: boolean };
};

export type DetailSpec = {
  sparkline?: { data_path?: string; color?: string; height?: number; max_points?: number; variant?: "bar" | "line" };
  metadata?: { label: string; path?: string; render_as?: string; zone?: "config" | "identity" }[];
  tabs?: { id: string; label: string; tool?: string; args?: Record<string, string> }[];
};

export type ItemListProps = {
  data_tool?: string;
  refresh_ms?: number;
  data_path?: string;
  item_key?: string;
  empty_icon?: string;
  empty_message?: string;
  header?: {
    icon?: string;
    stats_tool?: string;
    stats_map?: Record<string, string>;
  };
  filters?: FilterBarProps & { field?: string; values?: string[]; colors?: Record<string, string> };
  item_layout?: ItemLayoutSpec;
  item_snapshot_tool?: string;
  item_snapshot_args?: Record<string, string>;
  snapshot_merge_path?: string;
  detail?: DetailSpec;
};

/* ── Helpers ── */

export function extractArray(raw: unknown, dataPath?: string): Record<string, unknown>[] {
  if (dataPath && raw && typeof raw === "object") {
    const extracted = resolve(raw as Record<string, unknown>, dataPath);
    if (Array.isArray(extracted)) return extracted as Record<string, unknown>[];
  }
  if (Array.isArray(raw)) return raw as Record<string, unknown>[];
  return [];
}
