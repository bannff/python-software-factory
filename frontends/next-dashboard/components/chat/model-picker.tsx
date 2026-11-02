"use client";

import { useCallback, useMemo, useState } from "react";
import { Cpu, RefreshCw, Search } from "lucide-react";
import { useAgent } from "@copilotkit/react-core/v2";
import { useCopilotKit } from "@copilotkit/react-core/v2";
import { Popover } from "@/components/ui/popover";
import { callTool } from "@/lib/api";
import { effectiveLabel } from "@/lib/model-catalog";
import { useModelCatalog } from "@/lib/hooks/use-model-catalog";
import { useSessionList } from "@/lib/hooks/use-session-list";
import { useChatPreferences } from "@/components/settings/use-chat-preferences";
import { cn } from "@/lib/utils";
import { ModelGroupList } from "./model-group-list";

/**
 * Mixed-provider chat-model picker (M6.5 slice 4). Groups Bedrock, OpenRouter,
 * Ollama, and openai-compat entries by provider without assuming one catalog
 * shape.
 *
 * Scope: the catalog is deployment-scoped by default (#136), so the live
 * provider catalog is only offered behind the reveal control. The two
 * selectors that must always resolve — the session's own model and the pending
 * pick — are sent as ``include``, and the pill prints the EFFECTIVE model the
 * session row resolves to, never the raw stored selector.
 *
 * Persistence: when the current thread has a PERSISTED Session, the pick is
 * written through owner-scoped Session CAS (``session_set_model`` with the
 * session's ``expected_revision``) FIRST; only on success does it merge
 * ``companion_x_model`` into CopilotKit properties. With no persisted Session,
 * it sets the next-session hint only and says so — never claiming a write that
 * did not happen. ``setProperties`` replaces wholesale, so we merge current
 * properties to avoid clobbering other forwarded props.
 */
export function ModelPicker({ agentId }: { agentId: string }) {
  const { copilotkit } = useCopilotKit();
  const { agent } = useAgent({ agentId });
  const { preferences } = useChatPreferences();
  const { sessions, refresh } = useSessionList(false);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [revealAsked, setRevealAsked] = useState(false);
  const [query, setQuery] = useState("");

  const active = useMemo(
    () => sessions.find((session) => session.thread_id === agent?.threadId),
    [sessions, agent?.threadId],
  );
  const { models, groups, loading, error, scope, hiddenCount, unresolved, refresh: refreshCatalog, revealAll } =
    useModelCatalog({ include: [active?.model, activeModel] });
  const visibleGroups = useMemo(() => groups.map((group) => ({
    ...group,
    models: group.models.filter((model) => !preferences.hiddenModels.includes(model.model_id)),
  })).filter((group) => group.models.length > 0), [groups, preferences.hiddenModels]);

  const pick = useCallback(async (modelId: string) => {
    const current = (copilotkit?.properties ?? {}) as Record<string, unknown>;
    if (active) {
      setPending(true);
      setStatus(null);
      try {
        await callTool("session_set_model", {
          session_id: active.session_id, model: modelId, expected_revision: active.revision,
        });
        copilotkit?.setProperties({ ...current, companion_x_model: modelId });
        setActiveModel(modelId);
        refresh();
      } catch {
        setStatus("Couldn’t switch model — this session may have changed. Reopen it and retry.");
      } finally {
        setPending(false);
      }
    } else {
      copilotkit?.setProperties({ ...current, companion_x_model: modelId });
      setActiveModel(modelId);
      setStatus("Applies to your next session.");
    }
  }, [active, copilotkit, refresh]);

  const selectedModelId = activeModel ?? active?.model ?? null;
  // Resolution is impossible while the catalog is in flight or unavailable, so
  // only a LOADED catalog may call a stored selector unresolvable (#136).
  const resolved = effectiveLabel(models, selectedModelId);
  const unresolvable = selectedModelId !== null && !loading && !error && resolved === null;
  const storedSelector = selectedModelId ?? "";
  const label = resolved?.effectiveModelId ?? (unresolvable ? "Unavailable" : selectedModelId ?? "Model");
  const pillTitle = unresolvable
    ? `${storedSelector} is not a resolvable model`
    : error && selectedModelId ? `Model catalog unavailable — showing ${storedSelector}` : "";
  const total = visibleGroups.reduce((sum, group) => sum + group.models.length, 0);
  // A deployment that pins the scope serves "configured" even after a reveal
  // request; saying so beats a button that looks live and does nothing.
  const revealStuck = revealAsked && scope === "configured";

  return (
    <Popover
      align="left"
      side="down"
      trigger={
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground/70" title="Choose the chat model">
          <Cpu className="h-3 w-3" />
          <span className={cn("max-w-[110px] truncate", unresolvable && "text-destructive/80")} title={pillTitle || undefined}>
            {label}
          </span>
        </span>
      }
    >
      <div className="flex w-72 flex-col gap-1">
        <div className="flex items-center justify-between gap-2 px-1 pb-1">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/60">
            {active ? "Model · this session" : "Model · next session"}
          </span>
          <button type="button" onClick={() => refreshCatalog(true)} disabled={loading}
            aria-label="Refresh model catalog" title="Re-fetch the provider model list"
            className="rounded p-0.5 text-muted-foreground/60 hover:text-foreground disabled:opacity-40">
            <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
          </button>
        </div>
        {total > 8 && <label className="flex items-center gap-1.5 rounded-md border border-border/50 px-2">
          <Search className="h-3 w-3 text-muted-foreground/60" />
          <span className="sr-only">Search models</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${total} models`}
            className="w-full bg-transparent py-1 text-xs outline-none" autoFocus />
        </label>}
        {loading && <div className="px-2 py-1.5 text-muted-foreground/60">Loading…</div>}
        {error && !loading && <div className="px-2 py-1.5 text-destructive/80">{error}</div>}
        {pending && <div role="status" className="px-2 py-1 text-muted-foreground/60">Switching…</div>}
        {status && <div role="status" className="px-2 py-1 text-[10px] text-muted-foreground/70">{status}</div>}
        {!loading && !error && unresolved.length > 0 && (
          <div className="px-2 py-1 text-[10px] text-muted-foreground/70">
            Not available here: {unresolved.join(", ")}
          </div>)}
        {!loading && !error && hiddenCount > 0 && scope === "configured" && (
          <button type="button" disabled={revealStuck} onClick={() => { setRevealAsked(true); revealAll(); }}
            title={revealStuck
              ? "This deployment serves the scoped catalog only"
              : "Load the models this deployment does not configure"}
            className="rounded-md border border-border/50 px-2 py-1 text-left text-[10px] text-muted-foreground/80 hover:text-foreground disabled:opacity-60">
            Show all {hiddenCount} hidden models
          </button>)}
        {!loading && !error && <ModelGroupList groups={visibleGroups} query={query}
          selectedModelId={selectedModelId} disabled={pending} onPick={(id) => void pick(id)} />}
      </div>
    </Popover>
  );
}
