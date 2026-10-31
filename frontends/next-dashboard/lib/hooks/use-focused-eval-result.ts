"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

const MISSING_RESULT_RETRY_DELAY_MS = 2_000;
const MAX_MISSING_RESULT_RETRIES = 5;

export interface EvalRunResult {
  run_id?: string;
  verdict?: string;
  pass_rate?: number;
  avg_score?: number;
  total_cases?: number;
  passed?: number;
  passed_cases?: number;
  duration_ms?: number;
  evaluators_used?: string[];
  case_results?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

interface FocusedEvalResultState {
  loading: boolean;
  waiting: boolean;
  error: string | null;
  found: boolean;
  result: EvalRunResult | null;
}

const EMPTY_STATE: FocusedEvalResultState = {
  loading: false,
  waiting: false,
  error: null,
  found: false,
  result: null,
};

export function useFocusedEvalResult(runId: string | null) {
  const [state, setState] = useState<FocusedEvalResultState>(EMPTY_STATE);
  const [refreshKey, setRefreshKey] = useState(0);
  const requestRef = useRef(0);
  const refresh = useCallback(() => {
    requestRef.current += 1;
    setRefreshKey((key) => key + 1);
  }, []);

  useEffect(() => {
    if (!runId) {
      requestRef.current += 1;
      setState(EMPTY_STATE);
      return;
    }

    const request = ++requestRef.current;
    let retries = 0;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const isCurrent = () => request === requestRef.current;
    const fetchResult = async (): Promise<void> => {
      if (!isCurrent()) return;
      try {
        const raw = await callTool("evals_get_run_result", { run_id: runId });
        if (!isCurrent()) return;
        const data = unwrapToolData(raw) as { found?: boolean; result?: EvalRunResult | null };
        if (data?.found === true) {
          setState({ loading: false, waiting: false, error: null, found: true, result: data.result ?? null });
          return;
        }
        if (data?.found !== false || retries >= MAX_MISSING_RESULT_RETRIES) {
          setState({ loading: false, waiting: false, error: null, found: false, result: null });
          return;
        }
        retries += 1;
        setState({ loading: true, waiting: true, error: null, found: false, result: null });
        retryTimer = setTimeout(() => {
          retryTimer = undefined;
          void fetchResult();
        }, MISSING_RESULT_RETRY_DELAY_MS);
      } catch (error) {
        if (!isCurrent()) return;
        setState({
          loading: false,
          waiting: false,
          error: error instanceof Error ? error.message : "Eval result unavailable",
          found: false,
          result: null,
        });
      }
    };

    setState({ loading: true, waiting: false, error: null, found: false, result: null });
    void fetchResult();
    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      if (isCurrent()) requestRef.current += 1;
    };
  }, [refreshKey, runId]);

  return { ...state, refresh };
}
