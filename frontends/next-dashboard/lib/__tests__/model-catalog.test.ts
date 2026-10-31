import { describe, expect, it } from "vitest";
import {
  applyRenderCap, cheapestModelId, effectiveLabel, formatPricing, groupByProvider,
  parseCatalog, type ProviderGroup,
} from "../model-catalog";

const modelsOf = (raw: unknown) => parseCatalog(raw).models;

describe("parseCatalog scope fields (#136)", () => {
  it("carries the served scope, the withheld count and unresolved selectors", () => {
    const catalog = parseCatalog({ ok: true, data: {
      count: 1, scope: "all", hidden_count: 452, unresolved: ["openrouter/retired"],
      models: [{ model_id: "openrouter", provider: "openrouter", model: "deepseek/v4.1",
        effective_model_id: "openrouter/deepseek/v4.1", configured: true }],
    } });
    expect(catalog.scope).toBe("all");
    expect(catalog.hiddenCount).toBe(452);
    expect(catalog.unresolved).toEqual(["openrouter/retired"]);
    expect(catalog.models[0].configured).toBe(true);
    expect(catalog.models[0].effectiveModelId).toBe("openrouter/deepseek/v4.1");
  });

  it("defaults an older server's missing fields truthfully instead of guessing", () => {
    const catalog = parseCatalog({ ok: true, data: { count: 1, models: [
      { model_id: "anthropic.claude", provider: "bedrock", model: "anthropic.claude" },
    ] } });
    expect(catalog.scope).toBe("configured");
    expect(catalog.hiddenCount).toBe(0);
    expect(catalog.unresolved).toEqual([]);
    expect(catalog.models[0].configured).toBe(true);
    expect(catalog.models[0].effectiveModelId).toBe("bedrock/anthropic.claude");
  });

  it("keeps a row the deployment did not configure marked as such", () => {
    const [row] = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "openrouter/openai/gpt-5", provider: "openrouter", model: "openai/gpt-5",
        effective_model_id: "openrouter/openai/gpt-5", configured: false },
    ] } });
    expect(row.configured).toBe(false);
  });
});

describe("effectiveLabel resolves the pill's selector (#136)", () => {
  const models = modelsOf({ ok: true, data: { count: 2, models: [
    { model_id: "openrouter", provider: "openrouter", model: "deepseek/deepseek-v4.1-flash",
      effective_model_id: "openrouter/deepseek/deepseek-v4.1-flash", configured: true },
    { model_id: "anthropic.claude", provider: "bedrock", model: "anthropic.claude",
      effective_model_id: "bedrock/anthropic.claude", configured: true },
  ] } });

  it("resolves a raw selector to the model that will actually run", () => {
    expect(effectiveLabel(models, "openrouter")?.effectiveModelId)
      .toBe("openrouter/deepseek/deepseek-v4.1-flash");
  });

  it("resolves a selector stored before the change as a provider-native id", () => {
    expect(effectiveLabel(models, "openrouter/deepseek/deepseek-v4.1-flash")?.model_id)
      .toBe("openrouter");
  });

  it("returns null for a selector no loaded catalog row resolves", () => {
    expect(effectiveLabel(models, "openrouter/retired-model")).toBeNull();
    expect(effectiveLabel(models, null)).toBeNull();
  });
});

describe("applyRenderCap", () => {
  const wide: ProviderGroup[] = [{ provider: "openrouter", models: Array.from({ length: 453 }, (_, i) => ({
    model_id: `openrouter/v${i}`, provider: "openrouter", model: `v${i}`,
    effectiveModelId: `openrouter/v${i}`, configured: false,
  })) }];

  it("renders the cap and reports how many rows it withheld", () => {
    const { groups, hidden } = applyRenderCap(wide);
    expect(groups[0].models).toHaveLength(40);
    expect(hidden).toBe(413);
  });

  it("spends the cap across groups and keeps the filtered count honest", () => {
    const { groups, hidden } = applyRenderCap([
      { provider: "bedrock", models: wide[0].models.slice(0, 30) },
      { provider: "openrouter", models: wide[0].models.slice(30, 70) },
    ], 40);
    expect(groups.map((group) => group.models.length)).toEqual([30, 10]);
    expect(hidden).toBe(30);
  });

  it("leaves a small catalog untouched", () => {
    const { groups, hidden } = applyRenderCap([{ provider: "bedrock", models: wide[0].models.slice(0, 2) }]);
    expect(groups[0].models).toHaveLength(2);
    expect(hidden).toBe(0);
  });
});

describe("parseCatalog pricing extraction", () => {
  it("carries pricing when both fields are numbers", () => {
    const models = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "openrouter/x", provider: "openrouter", model: "x",
        prompt_usd_per_token: 0.0000002, completion_usd_per_token: 0.0000008 },
    ] } });
    expect(models[0].promptUsdPerToken).toBe(0.0000002);
    expect(models[0].completionUsdPerToken).toBe(0.0000008);
  });

  it("omits pricing fields entirely when the server sends null (non-OpenRouter provider)", () => {
    const models = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "anthropic.claude", provider: "bedrock", model: "anthropic.claude",
        prompt_usd_per_token: null, completion_usd_per_token: null },
    ] } });
    expect(models[0].promptUsdPerToken).toBeUndefined();
    expect(models[0].completionUsdPerToken).toBeUndefined();
  });
});

describe("cheapestModelId", () => {
  it("picks the lowest blended cost among priced models", () => {
    const models = modelsOf({ ok: true, data: { count: 2, models: [
      { model_id: "openrouter/expensive", provider: "openrouter", model: "expensive",
        prompt_usd_per_token: 0.00001, completion_usd_per_token: 0.00005 },
      { model_id: "openrouter/cheap", provider: "openrouter", model: "cheap",
        prompt_usd_per_token: 0.0000001, completion_usd_per_token: 0.0000004 },
    ] } });
    expect(cheapestModelId(models)).toBe("openrouter/cheap");
  });

  it("returns null when nothing has pricing", () => {
    const models = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "anthropic.claude", provider: "bedrock", model: "anthropic.claude" },
    ] } });
    expect(cheapestModelId(models)).toBeNull();
  });

  it("ignores unpriced entries when ranking priced ones", () => {
    const models = modelsOf({ ok: true, data: { count: 2, models: [
      { model_id: "anthropic.claude", provider: "bedrock", model: "anthropic.claude" },
      { model_id: "openrouter/x", provider: "openrouter", model: "x",
        prompt_usd_per_token: 0.0000001, completion_usd_per_token: 0.0000004 },
    ] } });
    expect(cheapestModelId(models)).toBe("openrouter/x");
  });
});

describe("formatPricing", () => {
  it("formats per-million pricing for both directions", () => {
    const [model] = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "openrouter/x", provider: "openrouter", model: "x",
        prompt_usd_per_token: 0.0000002, completion_usd_per_token: 0.0000008 },
    ] } });
    expect(formatPricing(model)).toBe("$0.20/M in · $0.80/M out");
  });

  it("returns null when pricing is absent", () => {
    const [model] = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "anthropic.claude", provider: "bedrock", model: "anthropic.claude" },
    ] } });
    expect(formatPricing(model)).toBeNull();
  });

  it("labels a genuinely free model rather than showing $0.00", () => {
    const [model] = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "openrouter/free-model", provider: "openrouter", model: "free-model",
        prompt_usd_per_token: 0, completion_usd_per_token: 0 },
    ] } });
    expect(formatPricing(model)).toBe("free in · free out");
  });
});

describe("groupByProvider keeps per-choice fields", () => {
  it("preserves pricing, the effective id and the configured flag through grouping", () => {
    const models = modelsOf({ ok: true, data: { count: 1, models: [
      { model_id: "openrouter/x", provider: "openrouter", model: "x",
        effective_model_id: "openrouter/x", configured: false,
        prompt_usd_per_token: 0.0000002, completion_usd_per_token: 0.0000008 },
    ] } });
    const [group] = groupByProvider(models);
    expect(group.models[0].promptUsdPerToken).toBe(0.0000002);
    expect(group.models[0].effectiveModelId).toBe("openrouter/x");
    expect(group.models[0].configured).toBe(false);
  });
});
