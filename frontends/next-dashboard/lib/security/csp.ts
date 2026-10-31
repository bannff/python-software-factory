/**
 * CSP and companion security headers for the Next dashboard.
 *
 * CSP remains pure so middleware can bind a per-request nonce while tests pin
 * directives without a Next runtime. Static config emits only non-CSP headers:
 * the middleware is the sole CSP owner for document requests.
 */

export interface SecurityHeader {
  key: string;
  value: string;
}

/** Resolve only the public API origin; internal proxy URLs must not reach CSP. */
function resolveApiOrigin(): string {
  const url = process.env.NEXT_PUBLIC_API_URL || "";
  if (!url) return "";
  try {
    return new URL(url).origin;
  } catch {
    return "";
  }
}

/** Build a CSP, optionally bound to a document nonce by Edge middleware. */
export function buildContentSecurityPolicy(nonce?: string): string {
  const isProd = process.env.NODE_ENV === "production";
  const apiOrigin = resolveApiOrigin();
  const nonceSource = nonce ? ` 'nonce-${nonce}'` : "";
  const scriptSrc = isProd
    ? `'self'${nonceSource} 'strict-dynamic' 'wasm-unsafe-eval'`
    : `'self'${nonceSource} 'wasm-unsafe-eval' 'unsafe-inline' 'unsafe-eval'`;
  // Next Themes and runtime UI styles do not all carry a nonce. This preserves
  // the dashboard's pre-existing style allowance without weakening scripts.
  const styleSrc = "'self' 'unsafe-inline'";
  const connectSrc = (isProd
    ? ["'self'", "https:", "wss:", apiOrigin]
    : ["'self'", "https:", "wss:", "ws:", "http:", apiOrigin]
  )
    .filter(Boolean)
    .join(" ");

  const directives: Array<[string, string]> = [
    ["default-src", "'self'"],
    ["script-src", scriptSrc],
    ["script-src-attr", "'none'"],
    ["style-src", styleSrc],
    // React and Framer Motion intentionally use style attributes.
    ["style-src-attr", "'unsafe-inline'"],
    ["img-src", "'self' data: blob:"],
    ["font-src", "'self' data:"],
    ["frame-src", "'self'"],
    ["frame-ancestors", "'self'"],
    ["connect-src", connectSrc],
    ["worker-src", "'self' blob:"],
    ["object-src", "'none'"],
    ["base-uri", "'self'"],
    ["form-action", "'self'"],
  ];
  return directives.map(([key, value]) => `${key} ${value}`).join("; ");
}

/** Build the Permissions-Policy string. */
export function buildPermissionsPolicy(): string {
  return ["camera=()", "microphone=()", "geolocation=()", "payment=()"].join(
    ", ",
  );
}

/** Static security headers; CSP belongs exclusively to middleware.ts. */
export function buildSecurityHeaders(): SecurityHeader[] {
  return [
    { key: "X-Frame-Options", value: "SAMEORIGIN" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: buildPermissionsPolicy() },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    { key: "Cross-Origin-Embedder-Policy", value: "credentialless" },
  ];
}
