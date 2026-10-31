"use client";

/**
 * Per-tool CopilotKit v2 render hooks.
 *
 * Split out of tool-renderers.tsx to keep both files under budget.
 * Each hook calls useRenderTool() once on mount and must live inside
 * a component tree under <CopilotKitProvider>.
 *
 * Note: the shell HITL approval card is NOT here — it's rendered by
 * useHumanInTheLoop("fe_approve_shell") in frontend-tools.tsx, the
 * framework-native HITL pattern (bd:python-factory-wog0b).
 */

import { useRenderTool } from "@copilotkit/react-core/v2";
import { z } from "zod";
import { Compass, Search, Database } from "lucide-react";
import { ToolCallCard, parseResult } from "./tool-call-card";
import { KbSearchCard, CacheGetCard } from "./tool-renderer-cards";

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/* kb_search ---------------------------------------------------------- */

const KbSearchArgs = z.object({
  query: z.string().optional(),
  limit: z.number().optional(),
});

export function useKbSearchRenderer() {
  useRenderTool({
    name: "kb_search",
    parameters: KbSearchArgs,
    render: ({ status, result }) => {
      const parsed = parseResult(result);
      const hits = Array.isArray(parsed) ? (parsed as Array<{ content?: string }>) : [];
      const top = hits[0]?.content;
      const preview = status === "complete"
        ? hits.length === 0
          ? "No results"
          : `${hits.length} result${hits.length === 1 ? "" : "s"}${top ? ` · ${truncate(top, 60)}` : ""}`
        : undefined;
      return (
        <ToolCallCard
          name="kb_search"
          title="Knowledge Base Search"
          status={status}
          icon={<Search className="h-3.5 w-3.5" />}
          previewLine={preview}
        >
          {status === "complete" ? <KbSearchCard results={hits as never} /> : null}
        </ToolCallCard>
      );
    },
  });
}

/* cache_get ---------------------------------------------------------- */

const CacheGetArgs = z.object({ key: z.string().optional() });

export function useCacheGetRenderer() {
  useRenderTool({
    name: "cache_get",
    parameters: CacheGetArgs,
    render: ({ status, result }) => {
      const parsed = parseResult(result) as
        | { key?: string; hit?: boolean }
        | undefined;
      const preview = status === "complete" && parsed
        ? `${parsed.key ?? "?"} · ${parsed.hit ? "HIT" : "MISS"}`
        : undefined;
      return (
        <ToolCallCard
          name="cache_get"
          title="Cache Lookup"
          status={status}
          icon={<Database className="h-3.5 w-3.5" />}
          previewLine={preview}
        >
          {status === "complete" && parsed
            ? <CacheGetCard data={parsed as never} />
            : null}
        </ToolCallCard>
      );
    },
  });
}

/* fe_navigate_canvas ------------------------------------------------- */

const NavigateCanvasArgs = z.object({
  view: z.string().optional(),
});

/**
 * Claims `fe_navigate_canvas` so the wildcard doesn't double up with
 * CopilotKit's built-in default renderer for `useFrontendTool`.
 */
export function useNavigateCanvasRenderer() {
  useRenderTool({
    name: "fe_navigate_canvas",
    parameters: NavigateCanvasArgs,
    render: ({ status, parameters }) => {
      const view = parameters?.view;
      const label = view ? truncate(view, 40) : "view";
      const preview =
        status === "complete"
          ? `Switched to ${label}`
          : status === "executing" || status === "inProgress"
            ? `Switching to ${label}…`
            : undefined;
      return (
        <ToolCallCard
          name="fe_navigate_canvas"
          title="Switch view"
          icon={<Compass className="h-3.5 w-3.5" />}
          status={status}
          previewLine={preview}
        />
      );
    },
  });
}
