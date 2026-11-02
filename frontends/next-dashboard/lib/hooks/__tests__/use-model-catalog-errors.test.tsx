import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const callTool = vi.fn();
vi.mock("@/lib/api", () => ({ callTool: (...args: unknown[]) => callTool(...args) }));

import { MODEL_NOT_CONFIGURED, useModelCatalog } from "@/lib/hooks/use-model-catalog";

function reasoned(reason: string): Error {
  return Object.assign(new Error("tool failed"), { reason });
}

describe("useModelCatalog error text", () => {
  it("names the missing configuration when nothing is configured yet", async () => {
    callTool.mockRejectedValue(reasoned("model_catalog_not_configured"));
    const { result } = renderHook(() => useModelCatalog());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe(MODEL_NOT_CONFIGURED);
    expect(MODEL_NOT_CONFIGURED).toBe(
      "No chat model configured yet: set COMPANION_X_CHAT_MODEL (or an openai-compat profile)",
    );
  });

  it("keeps the generic text for a real failure", async () => {
    callTool.mockRejectedValue(reasoned("model_catalog_unavailable"));
    const { result } = renderHook(() => useModelCatalog());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Model catalog unavailable");
  });
});
