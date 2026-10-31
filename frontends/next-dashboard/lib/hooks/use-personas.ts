"use client";

import { useCallback, useEffect, useState } from "react";
import { listPersonas } from "@/lib/api";
import type { Persona } from "@/lib/types";

interface UsePersonasResult {
  personas: Persona[];
  loading: boolean;
  error: string | null;
  /** Re-fetch on demand (e.g. when the palette opens). */
  refresh: () => void;
}

/**
 * Fetch chat personas from GET /api/personas (bd:python-factory-d4roe.3).
 *
 * The route is a thin read passthrough to the agent brick's
 * ``agent_get_agent_registry`` MCP tool, so this hook stays a plain
 * fetch with no MCP knowledge. Fetches once on mount and exposes
 * ``refresh`` so the palette can re-pull when a persona is created
 * at runtime (``agent_create_agent``). Failures degrade gracefully —
 * the palette just shows an empty/error state, chat keeps working on
 * the env-default persona.
 */
export function usePersonas(): UsePersonasResult {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    listPersonas()
      .then((res) => setPersonas(res.personas ?? []))
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load personas");
        setPersonas([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { personas, loading, error, refresh };
}
