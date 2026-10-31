"use client";

import React, { createContext, useCallback, useContext, useMemo, useRef } from "react";

/**
 * Refetch registry — authoritative client re-fetch after an action
 * (bd:3jcls.3, design decision 3).
 *
 * The action response deliberately does NOT carry a view payload; that would
 * fork view production between `*_get_views` and every operational tool. So
 * on success the dispatcher re-fetches. `useToolData` registers its `refetch`
 * here keyed by tool name; `ActionRef.invalidates` names the keys to fire.
 *
 * Optional by design: with no provider mounted, `invalidate` is a no-op and
 * the dispatch still works. That keeps the renderer usable in hosts (and
 * tests) that do not care about refresh.
 */

type RefetchFn = () => void;

interface InvalidationValue {
  register: (key: string, fn: RefetchFn) => () => void;
  invalidate: (keys: string[]) => void;
}

const InvalidationContext = createContext<InvalidationValue | null>(null);

export function InvalidationProvider({ children }: { children: React.ReactNode }) {
  // Multiple components can share a data_tool, so each key holds a Set.
  const registry = useRef(new Map<string, Set<RefetchFn>>());

  const register = useCallback((key: string, fn: RefetchFn) => {
    const map = registry.current;
    const existing = map.get(key) ?? new Set<RefetchFn>();
    existing.add(fn);
    map.set(key, existing);
    return () => {
      const current = map.get(key);
      if (!current) return;
      current.delete(fn);
      if (current.size === 0) map.delete(key);
    };
  }, []);

  const invalidate = useCallback((keys: string[]) => {
    for (const key of keys) {
      for (const fn of registry.current.get(key) ?? []) fn();
    }
  }, []);

  const value = useMemo(() => ({ register, invalidate }), [register, invalidate]);
  return (
    <InvalidationContext.Provider value={value}>{children}</InvalidationContext.Provider>
  );
}

/** Read the registry, or `null` when no provider is mounted. */
export function useInvalidation(): InvalidationValue | null {
  return useContext(InvalidationContext);
}

/**
 * Register a refetch under `key` for the component's lifetime. Called by
 * `useToolData` so `ActionRef.invalidates: ["cache_cache_stats"]` refreshes
 * every card reading that tool.
 */
export function useRegisterRefetch(key: string | undefined, refetch: RefetchFn): void {
  const invalidation = useInvalidation();
  const latest = useRef(refetch);
  latest.current = refetch;

  React.useEffect(() => {
    if (!key || !invalidation) return;
    return invalidation.register(key, () => latest.current());
  }, [key, invalidation]);
}
