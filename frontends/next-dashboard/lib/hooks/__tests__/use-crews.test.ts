import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const callTool = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ callTool }));

import { useCrews } from "../use-crews";

describe("useCrews", () => {
  it("keeps the failure reason instead of a constant", async () => {
    callTool.mockRejectedValue(new Error("gateway timeout"));
    const { result } = renderHook(() => useCrews());
    await waitFor(() => expect(result.current.error).toBe("gateway timeout"));
  });
});
