import { describe, expect, it } from "vitest";
import { MAX_NEIGHBOR_LIMIT, positiveLimit, unwrap } from "@/lib/graph-data-utils";

describe("Graph data transport boundaries", () => {
  it("fails closed on a typed failure envelope", () => {
    expect(() => unwrap({
      result: { ok: false, error: "backend unavailable" },
    })).toThrow("backend unavailable");
  });

  it("fails closed on bare and gateway-wrapped errors", () => {
    expect(() => unwrap({ error: "backend unavailable" })).toThrow("backend unavailable");
    expect(() => unwrap({
      ok: true,
      result: { structured_content: { schema_version: "v1", ok: false, error: { message: "denied" } } },
    })).toThrow("denied");
  });

  it("preserves successful domain data that includes an error field", () => {
    expect(unwrap({ error: "domain warning", count: 1 })).toEqual({
      error: "domain warning", count: 1,
    });
  });

  it("keeps client neighbor limits inside the server bound", () => {
    expect(positiveLimit(0)).toBe(1);
    expect(positiveLimit(2.9)).toBe(2);
    expect(positiveLimit(MAX_NEIGHBOR_LIMIT + 1)).toBe(MAX_NEIGHBOR_LIMIT);
  });
});
