/**
 * ActionRef — the frontend mirror of the server-side contract in
 * `components/ui/src/factory/ui/runtime/a2ui/actions.py` (bd:3jcls.3).
 *
 * There is deliberately no `url` / `href` / `method` / `endpoint` field. An
 * action can only ever name an MCP tool, and the server rejects the whole
 * declaration at view ingestion if a payload tries otherwise — so the
 * frontend never has to defend against a rogue target.
 *
 * The renderer receives ONE shape. Legacy `props.tool` strings emitted by 18
 * bricks are rewritten into `props.action` server-side, so there is no
 * back-compat branch here.
 */

/** The name of the single dispatch tool. See `ui/mcp/action_dispatch.py`. */
export const DISPATCH_TOOL = "ui_dispatch_action";

export interface ActionRef {
  /** Aggregator brick that owns the tool. */
  brick: string;
  /** Brick-local or brick-prefixed tool name. */
  tool: string;
  /** Literal arguments, merged first. */
  args?: Record<string, unknown>;
  /** `param -> "$.path"`, resolved against the row/form scope. */
  arg_bindings?: Record<string, string>;
  /** Human verb for the control. */
  label?: string | null;
  /** Require a confirm gesture before dispatch. */
  confirm?: boolean;
  /** View ids / `data_tool` names to refetch on success. */
  invalidates?: string[];
  /** Param that receives the per-gesture UUID, when the tool declares it. */
  idempotency_arg?: string | null;
}

/** Server response from `ui_dispatch_action`. */
export interface DispatchOutcome {
  ok: boolean;
  tool?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  error?: string;
  invalidates?: string[];
}

/** Narrow an unknown `props.action` value to an {@link ActionRef}. */
export function asActionRef(raw: unknown): ActionRef | null {
  if (!raw || typeof raw !== "object") return null;
  const candidate = raw as Partial<ActionRef>;
  if (typeof candidate.brick !== "string" || typeof candidate.tool !== "string") {
    return null;
  }
  return candidate as ActionRef;
}

/**
 * `$.`-prefixed dotted key walk — the same grammar `data_path` already uses
 * (`renderers/renderers-item-list-utils.ts:7`). No expressions, no
 * interpolation; the server validates the same shape at ingestion.
 */
export function resolveBinding(scope: Record<string, unknown>, path: string): unknown {
  if (!path.startsWith("$.")) return undefined;
  let current: unknown = scope;
  for (const key of path.slice(2).split(".")) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

/**
 * Build the argument object for a dispatch: literal `args`, overlaid with
 * every resolved `arg_bindings` entry, overlaid with the caller's extra args
 * (form field values). Bindings that resolve to `undefined` are dropped so a
 * missing row field does not send `undefined` over the wire.
 */
export function resolveArgs(
  action: ActionRef,
  scope: Record<string, unknown> = {},
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...(action.args ?? {}) };
  for (const [param, path] of Object.entries(action.arg_bindings ?? {})) {
    const value = resolveBinding(scope, path);
    if (value !== undefined) out[param] = value;
  }
  return { ...out, ...extra };
}

/**
 * Stable key for in-flight deduplication: the target plus its resolved
 * arguments. Two identical gestures collapse to one call; two different ones
 * do not. Object keys are sorted so `{a,b}` and `{b,a}` produce one key.
 */
export function dedupeKey(action: ActionRef, args: Record<string, unknown>): string {
  const sorted = Object.keys(args).sort().map((k) => [k, args[k]]);
  return `${action.brick}/${action.tool}#${JSON.stringify(sorted)}`;
}

/** Per-gesture UUID. Falls back when `crypto.randomUUID` is unavailable. */
export function gestureId(): string {
  const c = globalThis.crypto as { randomUUID?: () => string } | undefined;
  if (typeof c?.randomUUID === "function") return c.randomUUID();
  return `g-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
