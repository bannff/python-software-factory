import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ModelChoice, ProviderGroup } from "@/lib/model-catalog";
import { RENDER_CAP } from "@/lib/model-catalog";
import { ModelGroupList } from "../model-group-list";

const EXPENSIVE = { promptUsdPerToken: 0.00001, completionUsdPerToken: 0.00005 };
const CHEAP = { promptUsdPerToken: 0.0000001, completionUsdPerToken: 0.0000004 };

function row(index: number, pricing: Partial<ModelChoice> = {}): ModelChoice {
  return {
    model_id: `openrouter/vendor${index}`, provider: "openrouter", model: `model-${index}`,
    effectiveModelId: `openrouter/vendor${index}`, configured: false, ...pricing,
  };
}

function group(models: ModelChoice[]): ProviderGroup[] {
  return [{ provider: "openrouter", models }];
}

function renderList(groups: ProviderGroup[], query = "") {
  render(<ModelGroupList groups={groups} query={query} selectedModelId={null} disabled={false} onPick={vi.fn()} />);
}

describe("ModelGroupList render cap", () => {
  it("renders at most RENDER_CAP rows and says how many it withheld", () => {
    renderList(group(Array.from({ length: RENDER_CAP + 5 }, (_, i) => row(i))));
    expect(screen.getAllByRole("option")).toHaveLength(RENDER_CAP);
    expect(screen.getByText(`…and 5 more — keep typing to narrow`)).toBeTruthy();
  });

  it("renders no footer when the match fits", () => {
    renderList(group(Array.from({ length: 3 }, (_, i) => row(i))));
    expect(screen.queryByText(/keep typing to narrow/)).toBeNull();
  });
});

describe("ModelGroupList cheapest badge reflects every MATCHED row", () => {
  it("flags the cheapest priced row", () => {
    renderList(group([row(0, EXPENSIVE), row(1, CHEAP)]));
    expect(screen.getByText("model-1").closest("button")?.textContent).toContain("cheapest");
    expect(screen.getByText("model-0").closest("button")?.textContent).not.toContain("cheapest");
  });

  it("never flags a rendered row when the cheapest MATCH sits beyond the render cap", () => {
    const models = Array.from({ length: RENDER_CAP + 1 }, (_, i) => row(i, EXPENSIVE));
    models[RENDER_CAP] = row(RENDER_CAP, CHEAP);
    renderList(group(models));
    expect(screen.getAllByRole("option")).toHaveLength(RENDER_CAP);
    expect(screen.queryByText("cheapest")).toBeNull();
  });
});
