"use client";

import { useCallback, useEffect, useState } from "react";
import { callTool } from "@/lib/api";
import { parseRoster, type Crew } from "@/components/crews/crew-types";

/**
 * Read the caller's owner-scoped Crews and default pointer via the real
 * ``agent_list_crews`` MCP tool (no invented REST). Failures degrade to a
 * truthful error string; the gallery renders retry, never a fake empty.
 */
export function useCrews() {
  const [crews, setCrews] = useState<Crew[]>([]);
  const [defaultId, setDefaultId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const roster = parseRoster(await callTool("agent_list_crews", {}));
      setCrews(roster.crews);
      setDefaultId(roster.defaultId);
      setError(null);
    } catch {
      setError("Crews unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { crews, defaultId, loading, error, refresh };
}
