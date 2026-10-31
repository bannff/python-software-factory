"use client";

import { useCallback, useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface SessionSummary {
  session_id: string;
  thread_id: string;
  title: string;
  agent_id: string;
  model: string;
  updated_at: string;
  archived_at: string | null;
  revision: number;
  /** Materialized Crew binding (empty when the session is unmaterialized). */
  crew_id: string;
  /** Owner-partitioned memory namespace (empty when unmaterialized). */
  memory_scope: string;
  /** Sparse durable rank; null means the session is not pinned. */
  pinned_rank: number | null;
  unread: boolean;
  tags: string[];
  /** Row 9 (feature-map): ids of the messages pinned in this session. */
  pinned_message_ids: string[];
  /** Row 6 (feature-map): the folder this session is filed under ("" = unfiled). */
  folder: string;
  /** Row 18 (feature-map): the session's rolling conversation summary,
   * empty until generated. */
  summary: string;
}

function normalizeSession(value: unknown): SessionSummary | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const required = ["session_id", "thread_id", "title", "agent_id", "model", "updated_at"];
  if (!required.every((key) => typeof row[key] === "string") || !Number.isInteger(row.revision)) {
    return null;
  }
  return {
    ...(row as unknown as SessionSummary),
    crew_id: typeof row.crew_id === "string" ? row.crew_id : "",
    memory_scope: typeof row.memory_scope === "string" ? row.memory_scope : "",
    pinned_rank: typeof row.pinned_rank === "number" && Number.isFinite(row.pinned_rank)
      ? row.pinned_rank : null,
    unread: row.unread === true,
    tags: Array.isArray(row.tags) ? row.tags.filter((tag): tag is string => typeof tag === "string") : [],
    pinned_message_ids: Array.isArray(row.pinned_message_ids)
      ? row.pinned_message_ids.filter((id): id is string => typeof id === "string") : [],
    summary: typeof row.summary === "string" ? row.summary : "",
    folder: typeof row.folder === "string" ? row.folder : "",
  };
}

export function parseSession(raw: unknown): SessionSummary {
  const data = unwrapToolData(raw) as { session?: unknown };
  const session = normalizeSession(data?.session);
  if (!session) throw new Error("Session unavailable");
  return session;
}

export function parseSessions(raw: unknown): SessionSummary[] {
  const data = unwrapToolData(raw) as { sessions?: unknown };
  if (!data || !Array.isArray(data.sessions)) return [];
  return data.sessions.map(normalizeSession).filter((item): item is SessionSummary => item !== null);
}

export function useSessionList(includeArchived: boolean) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const raw = await callTool("session_list", { include_archived: includeArchived });
      setSessions(parseSessions(raw));
      setError(null);
    } catch {
      setError("Sessions unavailable");
    } finally {
      setLoading(false);
    }
  }, [includeArchived]);

  useEffect(() => { void refresh(); }, [refresh]);
  return { sessions, loading, error, refresh };
}
