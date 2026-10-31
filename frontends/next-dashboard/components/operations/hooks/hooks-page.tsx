"use client";

/**
 * Row 115 (feature-map) — /hooks: full-page hook manager.
 *
 * Honest scaffold (owner ruling 16:20). The upstream KiroCrew `/hooks` page
 * managed a persistent hook registry backed by `GET,POST /api/hooks` +
 * `GET /api/kiro-hooks`. Companion-X has NO such persistent registry on this
 * port: webhooks here are ephemeral agent handoffs created at runtime via the
 * `register_hook` MCP tool (an external system POSTs back into a dedicated
 * session), not durable, user-managed hook definitions. So this operator
 * surface documents the available mechanism and renders an empty registry,
 * rather than faking CRUD over a store that does not exist. Wiring a
 * persistent hook store + `/api/hooks` endpoints is deferred (needs backend).
 */
export function HooksPage() {
  return (
    <div className="flex h-full min-h-0 flex-col p-6" aria-label="Hooks manager">
      <h1 className="mb-1 text-lg font-semibold">Hooks</h1>
      <p className="mb-4 text-sm text-muted-foreground">Webhook handoffs for this workspace.</p>

      <div className="rounded-md border border-border/40 p-4">
        <h2 className="text-sm font-medium">How hooks work here</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Webhooks are created at runtime by the agent via the <code>register_hook</code> tool: it
          returns a URL and a session key so an external system can POST results back into a
          dedicated session. They are ephemeral handoffs, not durable, user-managed definitions.
        </p>
      </div>

      <div className="mt-4 flex-1 rounded-md border border-dashed border-border/40 p-4">
        <h2 className="text-sm font-medium">Registered hooks</h2>
        <p className="mt-2 text-xs italic text-muted-foreground/70">
          No persistent hook registry on this deployment. A managed hook store
          (<code>GET,POST /api/hooks</code>) is not yet wired.
        </p>
      </div>
    </div>
  );
}
