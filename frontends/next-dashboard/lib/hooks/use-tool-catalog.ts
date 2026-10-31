"use client";

/**
 * Fetch the tool catalog on FIRST palette open, then keep it (bd:3jcls.4).
 *
 * Deferred because the server loads ~40 bricks in-process to answer, which is
 * the cost of a complete registry; paying it at app boot would slow every
 * session that never presses Cmd-K. Paying it once, on first open, is the
 * right trade — after that the loader's `_tool_cache` makes it cheap.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchToolCatalog, type ToolCatalog } from "@/lib/tool-catalog";

export interface ToolCatalogState {
  catalog: ToolCatalog | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useToolCatalog(enabled: boolean): ToolCatalogState {
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const requested = useRef(false);

  const reload = useCallback(() => {
    requested.current = false;
    setNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!enabled || requested.current) return;
    requested.current = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchToolCatalog(controller.signal)
      .then((next) => {
        setCatalog(next);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        requested.current = false;
        setError(err instanceof Error ? err.message : "Tool catalog unavailable");
        setLoading(false);
      });
    return () => controller.abort();
  }, [enabled, nonce]);

  return { catalog, loading, error, reload };
}
