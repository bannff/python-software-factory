/**
 * Dev-only hydration watchdog (GH #142).
 *
 * A Next.js dev server rejects `_next/*` internal traffic — including the HMR
 * websocket — for any host missing from its `allowedDevOrigins` allowlist
 * (`next/dist/server/lib/router-utils/block-cross-site-dev.js`). When that
 * handshake dies, React never reaches `hydrateRoot`: the server-rendered page
 * is there, the composer stays disabled on "Connecting to tools…", zero `/mcp`
 * requests are issued, and nothing actionable is logged. The browser does log
 * its own repeated HMR-socket failure (`WebSocket connection to
 * 'ws://<host>/_next/hmr…' failed: net::ERR_INVALID_HTTP_RESPONSE`), but that
 * names a URL, not the cause; the cause itself is only visible in the dev
 * server's own terminal.
 *
 * This inline script restores the missing signal. It cannot be a client
 * component: the whole point is that no React root ever mounts, so only a
 * script that runs during HTML parse can report the failure. It stays inert
 * while the app hydrates, and prints an actionable console error plus a
 * dismissible banner when the root is still absent after the grace period.
 *
 * Detection is intentionally hydration-based rather than origin-based: any
 * blocked-client failure (dead dev origin, a chunk that never executes) is
 * reported, and the message names the origin it was loaded from plus the
 * canonical loopback URL to use instead.
 */
export const DEV_HYDRATION_FLAG = "__companionXHydrationWatchdog";

/** Grace period after `load` before a missing React root is reported. */
export const DEV_HYDRATION_GRACE_MS = 10_000;

const DEV_HYDRATION_POLL_MS = 500;

/**
 * Source of the inline script rendered by `app/layout.tsx` in development.
 * Kept as a string (not a component) so it executes before — and regardless
 * of — the client bundle, and so it can be exercised directly by tests.
 */
export const DEV_HYDRATION_WATCHDOG_SCRIPT = `(function () {
  var FLAG = ${JSON.stringify(DEV_HYDRATION_FLAG)};
  if (window[FLAG]) return;
  window[FLAG] = true;
  var GRACE_MS = ${DEV_HYDRATION_GRACE_MS};
  var POLL_MS = ${DEV_HYDRATION_POLL_MS};

  function rootMounted() {
    var nodes = document.querySelectorAll("*");
    for (var i = 0; i < nodes.length; i++) {
      var keys = Object.keys(nodes[i]);
      for (var k = 0; k < keys.length; k++) {
        var key = keys[k];
        if (key.indexOf("__reactFiber$") === 0 || key.indexOf("__reactProps$") === 0) {
          return true;
        }
      }
    }
    return false;
  }

  function canonicalOrigin() {
    return location.protocol + "//localhost" + (location.port ? ":" + location.port : "");
  }

  function banner(canonical) {
    if (!document.body || document.body.querySelector("[data-companion-x-hydration-alert]")) return;
    var box = document.createElement("div");
    box.setAttribute("data-companion-x-hydration-alert", "");
    box.setAttribute("role", "alert");
    box.style.cssText = "position:fixed;z-index:2147483647;left:0;right:0;top:0;display:flex;"
      + "gap:12px;align-items:center;justify-content:center;padding:10px 16px;"
      + "background:#7f1d1d;color:#fff;font:13px/1.4 system-ui,sans-serif;text-align:center";
    var text = document.createElement("span");
    text.textContent = "This dashboard did not start: no React root mounted, no /mcp traffic. "
      + "Open " + canonical + " instead (a Next.js dev server only accepts its allowedDevOrigins hosts).";
    var link = document.createElement("a");
    link.href = canonical;
    link.textContent = "Open " + canonical;
    link.style.cssText = "color:#fff;font-weight:600;text-decoration:underline";
    var dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.textContent = "Dismiss";
    dismiss.style.cssText = "background:transparent;border:1px solid currentColor;color:inherit;"
      + "border-radius:4px;padding:2px 8px;cursor:pointer;font:inherit";
    dismiss.addEventListener("click", function () {
      if (box.parentNode) box.parentNode.removeChild(box);
    });
    box.appendChild(text);
    box.appendChild(link);
    box.appendChild(dismiss);
    document.body.appendChild(box);
  }

  function report() {
    var canonical = canonicalOrigin();
    console.error(
      "[companion-x] Dashboard did not start: the React root never mounted in this tab, so the "
      + "composer stays on \\u201cConnecting to tools\\u2026\\u201d and no /mcp requests are issued."
    );
    console.error(
      "[companion-x] Loaded from " + location.origin + ". A Next.js dev server rejects the HMR "
      + "websocket for any host missing from allowedDevOrigins (localhost, 127.0.0.1, [::1]); "
      + "hydration is then blocked with nothing actionable logged. Open " + canonical + " — see GH issue #142."
    );
    banner(canonical);
  }

  var started = false;
  function start() {
    if (started) return;
    started = true;
    var waited = 0;
    var timer = window.setInterval(function () {
      if (rootMounted()) {
        window.clearInterval(timer);
        return;
      }
      waited += POLL_MS;
      if (waited < GRACE_MS) return;
      window.clearInterval(timer);
      report();
    }, POLL_MS);
  }

  if (document.readyState === "complete") start();
  else window.addEventListener("load", start, { once: true });
})();`;
