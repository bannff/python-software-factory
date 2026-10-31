import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MockInstance } from "vitest";
// Next's own dev-origin predicate: the allowlist is only useful if this exact
// matcher accepts the hostname a browser sends in `Origin`.
import { isCsrfOriginAllowed } from "next/dist/server/app-render/csrf-protection";

import nextConfig from "@/next.config";
import {
  DEV_HYDRATION_FLAG,
  DEV_HYDRATION_GRACE_MS,
  DEV_HYDRATION_WATCHDOG_SCRIPT,
} from "@/lib/dev-hydration-watchdog";

/**
 * GH #142: a Next.js dev server that rejects this page's origin blocks
 * hydration with no browser-side signal at all — empty console, disabled
 * composer, zero `/mcp` traffic. The watchdog is the only reporter that can
 * run in that state, so its observable behaviour (not its source text) is
 * what these tests pin: it must stay silent once React mounts, and it must
 * print an actionable error plus a dismissible banner when the root never
 * appears.
 */

const ALERT_SELECTOR = "[data-companion-x-hydration-alert]";

/** Execute the exact script `app/layout.tsx` inlines, in this jsdom document. */
function runWatchdog(): void {
  new Function(DEV_HYDRATION_WATCHDOG_SCRIPT)();
}

/** The script arms on `load`; jsdom reports `complete`, so cover both paths. */
function signalLoaded(): void {
  window.dispatchEvent(new Event("load"));
}

function settle(): void {
  vi.advanceTimersByTime(DEV_HYDRATION_GRACE_MS + 2_000);
}

describe("dev origin allowlist", () => {
  // Next prepends `localhost` and `**.localhost` to whatever the config
  // provides (block-cross-site-dev.ts), so the config only has to contribute
  // the remaining loopback spellings.
  const allowedOrigins = [
    "localhost",
    "**.localhost",
    ...(nextConfig.allowedDevOrigins ?? []),
  ];

  it("admits every loopback host a local driver may open", () => {
    for (const host of ["localhost", "127.0.0.1", "[::1]"]) {
      expect(isCsrfOriginAllowed(host, allowedOrigins), host).toBe(true);
    }
  });

  it("does not admit non-loopback hosts, so the dev posture stays scoped", () => {
    for (const host of ["192.168.1.10", "evil.example.com", "0.0.0.0"]) {
      expect(isCsrfOriginAllowed(host, allowedOrigins), host).toBe(false);
    }
  });
});

describe("dev hydration watchdog", () => {
  let consoleError: MockInstance;

  beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = "";
    Reflect.deleteProperty(window, DEV_HYDRATION_FLAG);
    consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("reports a console error and a banner when no React root ever mounts", () => {
    runWatchdog();
    signalLoaded();
    settle();

    expect(consoleError).toHaveBeenCalled();
    expect(document.querySelector(ALERT_SELECTOR)).not.toBeNull();
  });

  it("names the canonical loopback origin in the report", () => {
    runWatchdog();
    signalLoaded();
    settle();

    const text = consoleError.mock.calls.flat().join("\n");
    expect(text).toContain(`//localhost:${location.port}`);
    expect(text).toContain("allowedDevOrigins");
  });

  it("stays silent while a mounted React root is present", () => {
    // React marks host nodes with an enumerable `__reactFiber$*` own property;
    // reproducing that marker is the whole hydration signal the script reads.
    document.body.appendChild(
      Object.assign(document.createElement("div"), { __reactFiber$probe: {} }),
    );
    runWatchdog();
    signalLoaded();
    settle();

    expect(consoleError).not.toHaveBeenCalled();
    expect(document.querySelector(ALERT_SELECTOR)).toBeNull();
  });

  it("does not report before the grace period elapses", () => {
    runWatchdog();
    signalLoaded();
    vi.advanceTimersByTime(DEV_HYDRATION_GRACE_MS - 2_000);

    expect(consoleError).not.toHaveBeenCalled();
    expect(document.querySelector(ALERT_SELECTOR)).toBeNull();
  });

  it("lets the driver dismiss the banner", () => {
    runWatchdog();
    signalLoaded();
    settle();

    const alert = document.querySelector<HTMLElement>(ALERT_SELECTOR);
    expect(alert).not.toBeNull();
    alert?.querySelector("button")?.click();

    expect(document.querySelector(ALERT_SELECTOR)).toBeNull();
  });
});
