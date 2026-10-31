import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { config, middleware } from "@/middleware";

describe("nonce CSP middleware", () => {
  it("overwrites inbound nonce and CSP values in both request and response", () => {
    const request = new NextRequest("https://dashboard.example/", {
      headers: {
        "Content-Security-Policy": "script-src *",
        "x-nonce": "attacker-controlled",
      },
    });
    const response = middleware(request);
    const policy = response.headers.get("Content-Security-Policy");
    const nonce = response.headers.get("x-middleware-request-x-nonce");

    expect(nonce).toBeTruthy();
    expect(nonce).not.toBe("attacker-controlled");
    expect(policy).toContain(`'nonce-${nonce}'`);
    expect(policy).not.toContain("script-src *");
    expect(response.headers.get("x-middleware-request-content-security-policy"))
      .toBe(policy);
    expect(response.headers.get("Cache-Control")).toBe("private, no-store, max-age=0");
  });

  it("matches document and RSC navigation requests but not API, static, or prefetches", () => {
    const matcher = config.matcher[0];

    expect(matcher.source).toContain("_next/static");
    expect(matcher.source).toContain("_next/image");
    expect(matcher.source).toContain("favicon.ico");
    expect(matcher.source).toContain("api");
    expect(matcher.missing).toEqual([
      { type: "header", key: "next-router-prefetch" },
      { type: "header", key: "purpose", value: "prefetch" },
    ]);
  });
});
