import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useGraphRunFocus } from "@/lib/hooks/use-graph-run-focus";

it("loads broad, exact, then broad topology as central focus changes", async () => {
  const broad = vi.fn(async () => {});
  const exact = vi.fn(async (_runId: string) => {});
  const { rerender } = renderHook(({ runId }) => useGraphRunFocus(runId, broad, exact), { initialProps: { runId: null as string | null } });
  expect(broad).toHaveBeenCalledTimes(1);
  expect(exact).not.toHaveBeenCalled();
  await act(async () => rerender({ runId: "full-run-id" }));
  expect(exact).toHaveBeenCalledWith("full-run-id");
  await act(async () => rerender({ runId: null }));
  expect(broad).toHaveBeenCalledTimes(2);
});
