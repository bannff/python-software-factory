"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { callTool } from "@/lib/api";
import {
  groupByProvider,
  parseCatalog,
  type CatalogScope,
  type ModelChoice,
  type ProviderGroup,
} from "@/lib/model-catalog";

interface ModelCatalog {
  models: ModelChoice[];
  groups: ProviderGroup[];
  loading: boolean;
  error: string | null;
  /** The scope the SERVER served — not necessarily the one requested. */
  scope: CatalogScope;
  /** Rows the scoping withheld; the reveal control renders only when > 0. */
  hiddenCount: number;
  /** Selectors this catalog could not resolve (a stored session model). */
  unresolved: string[];
  /** Re-read the catalog; `live` re-fetches the provider list, bypassing the cache. */
  refresh: (live?: boolean) => void;
  /** Ask for the full deployment catalog (the live provider catalog included). */
  revealAll: () => void;
}

interface ModelCatalogOptions {
  /** Initial projection. Authoring/governance lists pass "all"; pickers stay scoped. */
  scope?: CatalogScope;
  /** Selectors that must resolve whatever the scope (the session's own model). */
  include?: (string | null | undefined)[];
}

/**
 * Read the safe chat-model catalog via the delegated ``agent_list_models`` MCP
 * tool. The deployment-scoped projection is the default (#136), so a 450+ row
 * live provider catalog never masquerades as configured models; a caller that
 * needs the whole catalog asks for ``scope: "all"`` or calls ``revealAll``. An
 * unavailable catalog is a truthful error (degraded state) — never a fabricated
 * empty list — so a picker can say so instead of silently offering nothing.
 */
export function useModelCatalog(options: ModelCatalogOptions = {}): ModelCatalog {
  const includeKey = (options.include ?? []).filter(Boolean).join("\n");
  const include = useMemo(() => (includeKey ? includeKey.split("\n") : []), [includeKey]);
  const [models, setModels] = useState<ModelChoice[]>([]);
  const [requested, setRequested] = useState<CatalogScope>(options.scope ?? "configured");
  const [scope, setScope] = useState<CatalogScope>(options.scope ?? "configured");
  const [hiddenCount, setHiddenCount] = useState(0);
  const [unresolved, setUnresolved] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (live: boolean, wanted: CatalogScope) => {
    setLoading(true);
    try {
      const raw = await callTool("agent_list_models", {
        ...(live ? { refresh: true } : {}), scope: wanted,
        ...(include.length > 0 ? { include } : {}),
      });
      const catalog = parseCatalog(raw);
      setModels(catalog.models);
      setScope(catalog.scope);
      setHiddenCount(catalog.hiddenCount);
      setUnresolved(catalog.unresolved);
      setError(null);
    } catch {
      setModels([]);
      setHiddenCount(0);
      setUnresolved([]);
      setError("Model catalog unavailable");
    } finally {
      setLoading(false);
    }
  }, [include]);

  useEffect(() => {
    void load(false, requested);
  }, [load, requested]);

  const refresh = useCallback((live = false) => {
    void load(live, requested);
  }, [load, requested]);
  const revealAll = useCallback(() => setRequested("all"), []);

  const groups = useMemo(() => groupByProvider(models), [models]);
  return { models, groups, loading, error, scope, hiddenCount, unresolved, refresh, revealAll };
}
