"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { unwrapToolResult } from "../tool-result";
import { useBridge } from "../bridge-adapter-context";
import { useRegisterRefetch } from "../actions/invalidation-context";

/** Timeout (ms) for a single tool fetch attempt. */
const FETCH_TIMEOUT_MS = 10_000;
/** Number of retry attempts after the first failure. */
const MAX_RETRIES = 1;
/** Backoff delay (ms) before retrying. */
const RETRY_BACKOFF_MS = 2_000;

type ToolDataResult = {
  data: unknown;
  loading: boolean;
  error: string | null;
  refetch: () => void;
};

type UseToolDataOptions = {
  refreshMs?: number;
};

/** Wrap a promise with an AbortSignal-based timeout. */
function withTimeout<T>(promise: Promise<T>, ms: number, signal: AbortSignal): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Request timed out")), ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new Error("Aborted"));
    });
    promise.then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}

/** Sleep helper that respects abort. */
function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => { clearTimeout(timer); reject(new Error("Aborted")); });
  });
}

export function useToolData(
  toolName?: string,
  args: Record<string, unknown> = {},
  options: UseToolDataOptions = {},
): ToolDataResult {
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bridge = useBridge();

  const fetch_ = useCallback(async () => {
    if (!toolName) return;

    // Cancel any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    let lastErr: string | null = null;
    const attempts = 1 + MAX_RETRIES;

    for (let i = 0; i < attempts; i++) {
      if (controller.signal.aborted) break;
      try {
        if (i > 0) await sleep(RETRY_BACKOFF_MS, controller.signal);
        const res = await withTimeout(bridge.callTool(toolName, args), FETCH_TIMEOUT_MS, controller.signal);
        if (controller.signal.aborted) return;
        setData(unwrapToolResult(res));
        setLoading(false);
        return;
      } catch (err) {
        if (controller.signal.aborted) return;
        lastErr = err instanceof Error ? err.message : "Tool call failed";
      }
    }

    // All attempts exhausted
    if (!controller.signal.aborted) {
      setError(lastErr ?? "Tool call failed after retries");
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toolName, JSON.stringify(args), bridge]);

  useEffect(() => {
    fetch_();
    return () => { abortRef.current?.abort(); };
  }, [fetch_]);

  // Authoritative refresh after a human-fired action (bd:3jcls.3). An
  // ActionRef listing this tool in `invalidates` triggers `fetch_` — the
  // action response never carries a view payload, so the client re-fetches.
  useRegisterRefetch(toolName, fetch_);

  useEffect(() => {
    if (!toolName || !options.refreshMs || options.refreshMs <= 0) return;
    const id = setInterval(() => {
      void fetch_();
    }, options.refreshMs);
    return () => clearInterval(id);
  }, [fetch_, options.refreshMs, toolName]);

  return { data, loading, error, refetch: fetch_ };
}
