/**
 * CopilotKit v2 middleware for the @copilotkitnext/runtime endpoint at
 * `/api/copilotkit/agent/:agentId/run`. Wires beforeRequestMiddleware +
 * afterRequestMiddleware on the existing CopilotRuntime instance
 * (bd-47sl). bd-w5zk: scope intentionally trimmed to logging.
 *
 * Dispatcher source pin: @copilotkitnext/runtime@1.53.x.
 *   - runtime.d.cts:39-46 — middleware option types
 *   - middleware.mjs — callback-only dispatch in v1.53 (webhook URL
 *     form documented but unwired; logger.warn skips it)
 *   - middleware-sse-parser.mjs — afterRequest receives messages[]
 *     reconstructed from response stream ONLY. The user prompt is
 *     NOT in messages; only assistant + tool entries.
 *   - endpoints/hono-single.mjs — before-hook may short-circuit by
 *     returning a Response/Request; after-hook is fire-and-forget on
 *     c.res.clone() with .catch swallowed.
 *
 * Memory: strands-expert ebb89be9, meta-architect cc93db9c.
 *
 * The middleware fn types are not re-exported from the package's
 * public index, so we derive them from the public
 * `CopilotRuntimeOptions` shape rather than reaching into the
 * `./middleware` subpath (which is not in `package.json#exports`).
 */

import type { CopilotRuntimeOptions } from "@copilotkit/runtime/v2";

type BeforeRequestMiddlewareFn = NonNullable<
  CopilotRuntimeOptions["beforeRequestMiddleware"]
>;
type AfterRequestMiddlewareFn = NonNullable<
  CopilotRuntimeOptions["afterRequestMiddleware"]
>;

/**
 * Emits one structured log line for the inbound CopilotKit runtime
 * request. Returns `void` so the dispatcher does NOT short-circuit on
 * a returned Request — see `endpoints/hono-single.mjs`.
 */
export const requestLogger: BeforeRequestMiddlewareFn = ({ request, path }) => {
  console.log(
    JSON.stringify({
      stage: "before",
      method: request.method,
      path,
    }),
  );
};

/**
 * Emits one structured log line for the outbound CopilotKit runtime
 * response. `messages` is the SSE-reconstructed transcript (assistant
 * + tool entries only — the user prompt is never in this array).
 * We log COUNT only, never content, to keep the line PII-safe.
 */
export const responseLogger: AfterRequestMiddlewareFn = ({
  path,
  threadId,
  runId,
  messages,
}) => {
  console.log(
    JSON.stringify({
      stage: "after",
      path,
      threadId,
      runId,
      msgCount: messages?.length ?? 0,
    }),
  );
};
