import { afterEach, describe, expect, it } from "vitest";
import { getBuildId } from "../build-info";

const original = process.env.NEXT_PUBLIC_BUILD_ID;
afterEach(() => { process.env.NEXT_PUBLIC_BUILD_ID = original; });

describe("getBuildId (row 101, feature-map)", () => {
  it("returns the injected build id when set", () => {
    process.env.NEXT_PUBLIC_BUILD_ID = "abc1234-2026-09-17";
    expect(getBuildId()).toBe("abc1234-2026-09-17");
  });

  it("falls back to development when unset or blank", () => {
    delete process.env.NEXT_PUBLIC_BUILD_ID;
    expect(getBuildId()).toBe("development");
    process.env.NEXT_PUBLIC_BUILD_ID = "   ";
    expect(getBuildId()).toBe("development");
  });
});
