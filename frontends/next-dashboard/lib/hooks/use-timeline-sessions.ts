"use client";

import { useMemo } from "react";
import type { TimelineEntry } from "@/lib/types";
import { groupTimelineSessions, type SessionGroup } from "@/lib/timeline-sessions";

export type { SessionGroup } from "@/lib/timeline-sessions";

export function useTimelineSessions(entries: TimelineEntry[]): SessionGroup[] {
  return useMemo(() => groupTimelineSessions(entries), [entries]);
}
