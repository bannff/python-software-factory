import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useMounted } from "../use-mounted";

describe("useMounted", () => {
  it("is true while mounted and false after unmount", () => {
    const { result, unmount } = renderHook(() => useMounted());
    expect(result.current.current).toBe(true);
    unmount();
    expect(result.current.current).toBe(false);
  });
});
