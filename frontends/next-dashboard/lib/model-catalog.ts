import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * A non-secret chat-model choice, mirroring the llm_gateway
 * ``ChatModelDescriptor`` delegated through the agent brick's safe catalog.
 * Endpoints and credential-env names are never projected to the client.
 * ``effectiveModelId`` is the provider-native model the selector resolves to
 * (the pill's single source of truth, #136) and ``configured`` is false only
 * for rows that came from the live provider catalog rather than deployment
 * config. ``promptUsdPerToken``/``completionUsdPerToken`` are OpenRouter's own
 * public per-token USD pricing when the catalog has it — undefined for
 * providers with no comparable public pricing source (Bedrock, Ollama,
 * openai-compat).
 */
export interface ModelChoice {
  model_id: string;
  provider: string;
  model: string;
  effectiveModelId: string;
  configured: boolean;
  promptUsdPerToken?: number;
  completionUsdPerToken?: number;
}

export interface ProviderGroup {
  provider: string;
  models: ModelChoice[];
}

/** The projection the server actually served, and what it withheld. */
export interface ModelCatalogPayload {
  models: ModelChoice[];
  scope: CatalogScope;
  hiddenCount: number;
  unresolved: string[];
}

export type CatalogScope = "configured" | "all";

/** Unwrap + validate the ``agent_list_models`` ToolResult. */
export function parseCatalog(raw: unknown): ModelCatalogPayload {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const rows = Array.isArray(obj.models) ? obj.models : [];
  return {
    models: rows
      .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
      .filter((row) => typeof row.model_id === "string" && typeof row.provider === "string")
      .map((row) => {
        const model = typeof row.model === "string" ? row.model : (row.model_id as string);
        const provider = row.provider as string;
        return {
          model_id: row.model_id as string,
          provider,
          model,
          // An older server omits both #136 fields; both defaults are truthful.
          effectiveModelId: typeof row.effective_model_id === "string"
            ? row.effective_model_id : `${provider}/${model}`,
          configured: row.configured !== false,
          ...(typeof row.prompt_usd_per_token === "number" ? { promptUsdPerToken: row.prompt_usd_per_token } : {}),
          ...(typeof row.completion_usd_per_token === "number"
            ? { completionUsdPerToken: row.completion_usd_per_token } : {}),
        };
      }),
    scope: obj.scope === "all" ? "all" : "configured",
    hiddenCount: typeof obj.hidden_count === "number" ? obj.hidden_count : 0,
    unresolved: Array.isArray(obj.unresolved)
      ? obj.unresolved.filter((item): item is string => typeof item === "string") : [],
  };
}

/**
 * The row a stored selector actually runs (#136), or null when this catalog
 * cannot resolve it. Exact ``model_id`` match first, then ``effectiveModelId``:
 * the bare ``openrouter`` row and ``openrouter/<OPENROUTER_MODEL>`` collapse to
 * the same (provider, model) server-side, so the second match is required.
 */
export function effectiveLabel(models: ModelChoice[], selector: string | null): ModelChoice | null {
  if (!selector) return null;
  return models.find((model) => model.model_id === selector)
    ?? models.find((model) => model.effectiveModelId === selector)
    ?? null;
}

/**
 * Group choices by provider WITHOUT assuming one catalog shape — mixed
 * Bedrock, OpenRouter, Ollama, and openai-compat entries each fall into
 * their own group in first-seen order.
 */
export function groupByProvider(models: ModelChoice[]): ProviderGroup[] {
  const groups: ProviderGroup[] = [];
  const index = new Map<string, ProviderGroup>();
  for (const choice of models) {
    let group = index.get(choice.provider);
    if (!group) {
      group = { provider: choice.provider, models: [] };
      index.set(choice.provider, group);
      groups.push(group);
    }
    group.models.push(choice);
  }
  return groups;
}

/** Rendered-row ceiling: the revealed provider catalog can hold 450+ ids. */
export const RENDER_CAP = 40;

/**
 * Cap the rows actually RENDERED (never the matched set, so the footer can
 * still count what is hidden). A revealed live catalog stays scrollable
 * without a virtualization dependency (#136).
 */
export function applyRenderCap(
  groups: ProviderGroup[], cap = RENDER_CAP,
): { groups: ProviderGroup[]; hidden: number } {
  const capped: ProviderGroup[] = [];
  let budget = cap;
  let hidden = 0;
  for (const group of groups) {
    const visible = budget > 0 ? group.models.slice(0, budget) : [];
    budget -= visible.length;
    hidden += group.models.length - visible.length;
    if (visible.length > 0) capped.push(visible.length === group.models.length ? group : { ...group, models: visible });
  }
  return { groups: capped, hidden };
}

/** Blended per-token cost used to rank "cheapest" — 3:1 completion:prompt
 * weighting approximates a typical chat turn's token mix; not a bill. */
function blendedCost(model: ModelChoice): number | null {
  if (model.promptUsdPerToken === undefined || model.completionUsdPerToken === undefined) return null;
  return model.promptUsdPerToken + model.completionUsdPerToken * 3;
}

/** The model_id of the priced model with the lowest blended cost, if any priced model exists. */
export function cheapestModelId(models: ModelChoice[]): string | null {
  let best: { id: string; cost: number } | null = null;
  for (const model of models) {
    const cost = blendedCost(model);
    if (cost === null) continue;
    if (best === null || cost < best.cost) best = { id: model.model_id, cost };
  }
  return best?.id ?? null;
}

/** Human-readable per-million-token price, e.g. "$0.20/M in · $0.80/M out". */
export function formatPricing(model: ModelChoice): string | null {
  if (model.promptUsdPerToken === undefined || model.completionUsdPerToken === undefined) return null;
  const perMillion = (usdPerToken: number) => {
    const value = usdPerToken * 1_000_000;
    return value === 0 ? "free" : `$${value < 0.01 ? value.toFixed(4) : value.toFixed(2)}/M`;
  };
  return `${perMillion(model.promptUsdPerToken)} in · ${perMillion(model.completionUsdPerToken)} out`;
}
