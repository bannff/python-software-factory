"use client";

import { useCallback, useRef, useState } from "react";
import { useBridgeOptional } from "../bridge-adapter-context";
import { useInvalidation } from "./invalidation-context";
import { useTranscriptSink } from "./transcript-context";
import {
  DISPATCH_TOOL,
  type ActionRef,
  type DispatchOutcome,
  dedupeKey,
  gestureId,
  resolveArgs,
} from "./action-ref";

/**
 * useAction — THE frontend action dispatcher (bd:3jcls.3 / bd:372an).
 *
 * `ButtonRenderer` and `FormRenderer` both go through here. Neither one
 * touches `fetch` any more: before this hook they POSTed straight at
 * `/api/tools/${tool}`, bypassing the {@link BridgeAdapter} seam that every
 * other renderer hook honours, discarding the result and swallowing errors.
 * A grep canary test now fails the build if that pattern reappears.
 *
 * Everything routes through `bridge.callTool(DISPATCH_TOOL, ...)` — one
 * server-side chokepoint, which is also where the human provenance hint and
 * (later) the policy gate live.
 *
 * ## Delivery guarantee
 * When `ActionRef.idempotency_arg` is set AND the target tool's JSON schema
 * declares that param, the server receives a per-gesture UUID and the call is
 * genuinely idempotent for that gesture.
 *
 * Otherwise the guarantee is **at-most-once-per-gesture, not idempotent**:
 * an in-flight dedupe on `(tool, resolved args)` plus a `pending` flag the
 * caller uses to disable the control. A double-click cannot start two runs.
 * A reload, a second tab, or a repeat gesture with the same args CAN.
 */

export interface ActionState {
  pending: boolean;
  error: string | null;
  result: unknown;
  /** True once a dispatch has completed successfully at least once. */
  succeeded: boolean;
}

export interface UseActionResult extends ActionState {
  /**
   * Fire the action.
   *
   * @param action The validated {@link ActionRef} from `props.action`.
   * @param extra Caller-supplied arguments (form field values).
   * @param scope Row/form object that `arg_bindings` `$.` paths resolve against.
   */
  dispatch: (
    action: ActionRef,
    extra?: Record<string, unknown>,
    scope?: Record<string, unknown>,
  ) => Promise<DispatchOutcome>;
  reset: () => void;
}

const IDLE: ActionState = { pending: false, error: null, result: null, succeeded: false };

export function useAction(threadId?: string): UseActionResult {
  // Optional at render time, required at click time — a Button must still
  // paint in a host that mounted no provider (see `useBridgeOptional`).
  const bridge = useBridgeOptional();
  const invalidation = useInvalidation();
  const transcript = useTranscriptSink();
  const [state, setState] = useState<ActionState>(IDLE);
  // Shared across renders: collapses concurrent identical gestures.
  const inFlight = useRef(new Map<string, Promise<DispatchOutcome>>());

  const reset = useCallback(() => setState(IDLE), []);

  const dispatch = useCallback(
    async (
      action: ActionRef,
      extra: Record<string, unknown> = {},
      scope: Record<string, unknown> = {},
    ): Promise<DispatchOutcome> => {
      if (!bridge) {
        const error =
          "No BridgeAdapter mounted — wrap the tree in <BridgeAdapterProvider> " +
          "to dispatch actions.";
        setState({ pending: false, error, result: null, succeeded: false });
        return { ok: false, error };
      }
      const args = resolveArgs(action, scope, extra);
      const gesture = gestureId();
      if (action.idempotency_arg) args[action.idempotency_arg] = gesture;

      const key = dedupeKey(action, args);
      const existing = inFlight.current.get(key);
      if (existing) return existing;

      setState({ pending: true, error: null, result: null, succeeded: false });

      const run = (async (): Promise<DispatchOutcome> => {
        try {
          const raw = await bridge.callTool(DISPATCH_TOOL, {
            action,
            args,
            thread_id: threadId,
          });
          // The adapter is a pass-through; hooks own the envelope unwrap.
          const outcome = ((raw as { result?: unknown }).result ?? raw) as DispatchOutcome;
          if (!outcome || typeof outcome !== "object") {
            throw new Error("Dispatcher returned an unreadable response");
          }
          if (!outcome.ok) {
            // Visible, never swallowed — the defect bd:372an closed.
            setState({
              pending: false,
              error: outcome.error ?? "Action failed",
              result: null,
              succeeded: false,
            });
          } else {
            setState({
              pending: false, error: null, result: outcome.result, succeeded: true,
            });
            const keys = outcome.invalidates ?? action.invalidates ?? [];
            if (keys.length) invalidation?.invalidate(keys);
          }
          transcript?.({
            toolCallId: gesture,
            toolName: outcome.tool ?? action.tool,
            args,
            result: outcome.ok ? outcome.result : { error: outcome.error },
            ok: Boolean(outcome.ok),
          });
          return outcome;
        } catch (err) {
          const message = err instanceof Error ? err.message : "Action failed";
          setState({ pending: false, error: message, result: null, succeeded: false });
          transcript?.({
            toolCallId: gesture,
            toolName: action.tool,
            args,
            result: { error: message },
            ok: false,
          });
          return { ok: false, error: message };
        } finally {
          inFlight.current.delete(key);
        }
      })();

      inFlight.current.set(key, run);
      return run;
    },
    [bridge, invalidation, transcript, threadId],
  );

  return { ...state, dispatch, reset };
}
