/**
 * postMessage / onUIAction validator for the mcp-ui carrier (#5).
 *
 * Implements steps (3) Zod + (4) allowlist of the five-step pipeline
 * from security-engineer verdict
 * `d580bfdd-8928-47a4-8d73-a899328e128e` (bd:python-factory-lo1g9).
 * The pinned SDK enforces source-window equality before invoking
 * `onUIAction`; there is no host capture-phase message listener.
 * External URL origins are approved before rendering by
 * `OriginAllowlistGate`. This module is the schema + allowlist layer
 * around the callback payload.
 *
 * Dispatcher source pins (dev-principles.md "dispatcher source rule"):
 *   - `@mcp-ui/[email protected]/dist/index.mjs:175` — SDK does
 *     `m.source === u.current.contentWindow` strict equality before
 *     invoking our `onUIAction`. We add origin + Zod + allowlist on
 *     top.
 *   - `@mcp-ui/[email protected]/dist/src/types.d.ts` — `UIActionResult`
 *     discriminated union (`tool | prompt | link | intent | notify`).
 *   - `@mcp-ui/[email protected]/dist/index.mjs:2768` — mode dispatch by
 *     `mimeType` (text/html → rawHtml; text/uri-list → externalUrl;
 *     application/vnd.mcp-ui.remote-dom* → remoteDom).
 *
 * Allowlists are intentionally narrow (`@deterministic` read-only +
 * canvas-affecting intents). NEVER add `@authoring` or `@operational`
 * tools — chat tool gating elsewhere assumes our iframe cannot
 * mutate state. Verdict d580bfdd §4.
 */

import { z } from "zod";

/** Read-only tools the iframe is allowed to invoke directly. */
export const ALLOWED_IFRAME_TOOLS: readonly string[] = [
  "graph_get_app_topology",
  "kb_search",
  "memory_retrieve",
] as const;

/** Intents the iframe can dispatch into the host shell. */
export const ALLOWED_IFRAME_INTENTS: readonly string[] = [
  "navigate-canvas",
  "focus-finding",
  "expand-card",
] as const;

/* ----------------------------------------------------------------- */
/*  Zod discriminated union — mirrors @mcp-ui/[email protected] types       */
/* ----------------------------------------------------------------- */

const ToolCallSchema = z.object({
  type: z.literal("tool"),
  messageId: z.string().optional(),
  payload: z.object({
    toolName: z.string(),
    params: z.record(z.unknown()),
  }),
});

const PromptSchema = z.object({
  type: z.literal("prompt"),
  messageId: z.string().optional(),
  payload: z.object({ prompt: z.string() }),
});

const LinkSchema = z.object({
  type: z.literal("link"),
  messageId: z.string().optional(),
  payload: z.object({ url: z.string() }),
});

const IntentSchema = z.object({
  type: z.literal("intent"),
  messageId: z.string().optional(),
  payload: z.object({
    intent: z.string(),
    params: z.record(z.unknown()),
  }),
});

const NotifySchema = z.object({
  type: z.literal("notify"),
  messageId: z.string().optional(),
  payload: z.object({ message: z.string() }),
});

export const UIActionResultSchema = z.discriminatedUnion("type", [
  ToolCallSchema,
  PromptSchema,
  LinkSchema,
  IntentSchema,
  NotifySchema,
]);

export type ValidatedUIAction = z.infer<typeof UIActionResultSchema>;

/* ----------------------------------------------------------------- */
/*  Public validator                                                  */
/* ----------------------------------------------------------------- */

export type ValidationResult =
  | { ok: true; action: ValidatedUIAction }
  | { ok: false; reason: string };

/**
 * Run steps (3) + (4) of the pipeline.
 *
 *   3. Zod discriminatedUnion shape match
 *   4. ALLOWED_IFRAME_TOOLS / ALLOWED_IFRAME_INTENTS membership
 *
 * Before this function runs, the pinned SDK checks that the message
 * source is its rendered iframe. External URL origin admission happens
 * before rendering in `OriginAllowlistGate`; no host message listener
 * performs a second origin check. This function owns steps (3) + (4).
 */
export function validateUIAction(raw: unknown): ValidationResult {
  const parsed = UIActionResultSchema.safeParse(raw);
  if (!parsed.success) {
    return { ok: false, reason: `zod-shape: ${parsed.error.message}` };
  }
  const action = parsed.data;

  if (action.type === "tool") {
    if (!ALLOWED_IFRAME_TOOLS.includes(action.payload.toolName)) {
      return {
        ok: false,
        reason: `tool-not-allowlisted: ${action.payload.toolName}`,
      };
    }
  }

  if (action.type === "intent") {
    if (!ALLOWED_IFRAME_INTENTS.includes(action.payload.intent)) {
      return {
        ok: false,
        reason: `intent-not-allowlisted: ${action.payload.intent}`,
      };
    }
  }

  return { ok: true, action };
}

/**
 * Classify an mcp-ui resource mimeType into the renderer's three
 * modes. Mirrors the SDK's `Rt()` dispatch
 * (`@mcp-ui/[email protected]/dist/index.mjs:2762-2774`).
 *
 * Producer-side mimeTypes carry RFC 7231 parameters
 * (e.g. `text/html;profile=mcp-app`) that the SDK strict-equality
 * dispatch rejects, so the consumer normalizes by stripping
 * everything after `;`. The SDK treats the bare type as canonical.
 */
export function classifyMimeType(
  mimeType: string,
): "rawHtml" | "externalUrl" | "remoteDom" | null {
  const base = mimeType.split(";")[0]!.trim();
  if (base === "text/html") return "rawHtml";
  if (base === "text/uri-list") return "externalUrl";
  if (base.startsWith("application/vnd.mcp-ui.remote-dom")) return "remoteDom";
  return null;
}

/**
 * Normalize a producer-side mimeType to the bare value the SDK
 * accepts on its `He()` / `Rt()` strict-equality branches.
 *
 *   text/html;profile=mcp-app          → text/html
 *   application/vnd.mcp-ui.remote-dom+javascript;framework=react
 *                                      → application/vnd.mcp-ui.remote-dom+javascript (passthrough)
 *
 * The SDK only checks `r.mimeType !== "text/html"` and
 * `r.mimeType !== "text/uri-list"` at `index.mjs:21-22` — any RFC
 * 7231 parameter forwarded as-is is rejected with "Resource must
 * be of type text/html ...". For `application/vnd.mcp-ui.remote-dom*`
 * the SDK uses `startsWith` (`index.mjs:2772`) so passing the full
 * suffixed type is fine; but the framework parameter is read from
 * `r.mimeType.includes("framework=react")` so we MUST keep it.
 */
export function normalizeMimeTypeForSDK(mimeType: string): string {
  const base = mimeType.split(";")[0]!.trim();
  if (base === "text/html" || base === "text/uri-list") return base;
  // RemoteDOM keeps params — `framework=react` is read by the SDK.
  return mimeType;
}
