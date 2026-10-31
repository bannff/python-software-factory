import { describe, expect, it } from "vitest";

import { unwrapToolResult } from "../tool-result";

describe("unwrapToolResult", () => {
  it("unwraps nested JSON gateway and typed data envelopes", () => {
    expect(unwrapToolResult(JSON.stringify({
      result: JSON.stringify({ structured_content: JSON.stringify({ ok: true, data: { count: 2 } }) }),
    }))).toEqual({ count: 2 });
  });

  it("rejects typed and exactly bare transport failures", () => {
    expect(() => unwrapToolResult({ ok: false, error: { message: "denied" } })).toThrow("denied");
    expect(() => unwrapToolResult({ error: "unavailable" })).toThrow("unavailable");
  });

  it("preserves domain payloads that include an error field", () => {
    expect(unwrapToolResult({ error: "partial warning", count: 1 })).toEqual({
      error: "partial warning", count: 1,
    });
  });
});
