/**
 * Visual constants + tiny helpers for ``FindingsView`` — extracted so
 * the view file can fit the bd-F carrier #2 wiring under the 200-LOC
 * budget without losing any UX detail.
 */

import type { CSSProperties } from "react";
import type { FindingSeverity } from "@/lib/types";

export const SEV_ORDER: FindingSeverity[] = ["critical", "high", "medium", "low", "info"];

export const SEV_PILL_COLORS: Record<string, string> = {
  critical: "bg-red-500/10 text-red-400",
  high:     "bg-orange-500/10 text-orange-400",
  medium:   "bg-yellow-500/10 text-yellow-400",
  low:      "bg-blue-500/10 text-blue-400",
  info:     "bg-gray-500/10 text-gray-400",
};

export const SEV_BAR_COLORS: Record<string, string> = {
  critical: "bg-red-500",
  high:     "bg-orange-500",
  medium:   "bg-yellow-500",
  low:      "bg-blue-500",
  info:     "bg-gray-500",
};

export const SEV_CARD_GLOW: Record<string, CSSProperties> = {
  critical: {
    boxShadow: "0 0 0 1px rgba(239,68,68,0.3), 0 0 12px rgba(239,68,68,0.15)",
  },
  high: {
    boxShadow: "0 0 0 1px rgba(249,115,22,0.3), 0 0 12px rgba(249,115,22,0.1)",
  },
};

export const SEV_CARD_BG: Record<string, string> = {
  critical: "bg-red-950/10",
  high:     "bg-orange-950/[0.08]",
};

export const STRIDE_COLORS: Record<string, string> = {
  "Elevation of Privilege": "bg-red-500/10 text-red-400",
  "Information Disclosure":  "bg-yellow-500/10 text-yellow-400",
  "Denial of Service":       "bg-orange-500/10 text-orange-400",
  "Tampering":               "bg-orange-500/10 text-orange-400",
  "Spoofing":                "bg-gray-500/10 text-gray-400",
  "Repudiation":             "bg-purple-500/10 text-purple-400",
};

export function arnFragment(arn: string): string {
  const parts = arn.split(":");
  if (parts.length >= 6) return parts.slice(-2).join("/").slice(0, 40);
  return arn.slice(-40);
}
