import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  buildContentSecurityPolicy,
  buildPermissionsPolicy,
  buildSecurityHeaders,
} from "../csp";

describe("CSP — production nonce policy", () => {
  beforeEach(() => vi.stubEnv("NODE_ENV", "production"));
  afterEach(() => vi.unstubAllEnvs());

  it("binds strict script and style sources to the supplied nonce", () => {
    const csp = buildContentSecurityPolicy("test-nonce");

    expect(csp).toContain("script-src 'self' 'nonce-test-nonce' 'strict-dynamic' 'wasm-unsafe-eval'");
    expect(csp).toContain("style-src 'self' 'unsafe-inline'");
    expect(csp).toContain("script-src-attr 'none'");
    expect(csp).toContain("style-src-attr 'unsafe-inline'");
    const scriptSrc = csp.match(/script-src ([^;]+)/)?.[1] ?? "";
    expect(scriptSrc).not.toContain("'unsafe-eval'");
    expect(scriptSrc).not.toContain("'unsafe-inline'");
  });

  it("retains restrictive document, frame, and connection directives", () => {
    const csp = buildContentSecurityPolicy("test-nonce");

    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("frame-src 'self'");
    expect(csp).toContain("frame-ancestors 'self'");
    expect(csp).toContain("connect-src 'self' https: wss:");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("form-action 'self'");
  });

  it("does not expose a server-only proxy URL in the browser policy", () => {
    vi.stubEnv("API_URL", "http://companion_x-api:8000");

    expect(buildContentSecurityPolicy("test-nonce")).not.toContain("companion_x-api");
  });
});

describe("CSP — development compatibility", () => {
  beforeEach(() => vi.stubEnv("NODE_ENV", "development"));
  afterEach(() => vi.unstubAllEnvs());

  it("retains the Next development script allowances", () => {
    const csp = buildContentSecurityPolicy("test-nonce");

    expect(csp).toContain("'unsafe-inline'");
    expect(csp).toContain("'unsafe-eval'");
    expect(csp).toContain("connect-src 'self' https: wss: ws: http:");
  });
});

describe("companion security headers", () => {
  it("keeps CSP out of the static header bundle", () => {
    const map = Object.fromEntries(
      buildSecurityHeaders().map((header) => [header.key, header.value]),
    );

    expect(map).not.toHaveProperty("Content-Security-Policy");
    expect(map).toMatchObject({
      "X-Frame-Options": "SAMEORIGIN",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "strict-origin-when-cross-origin",
      "Permissions-Policy": buildPermissionsPolicy(),
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "credentialless",
    });
  });
});
