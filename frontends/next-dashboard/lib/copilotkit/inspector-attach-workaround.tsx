"use client";

/**
 * <InspectorAttachWorkaround /> — robust workaround for three bugs in
 * `@copilotkitnext/[email protected]`:
 *
 * 1. Initial-mount attach gap: `set core(value)` does not reliably
 *    fire `attachToCore` on the React-wrapper-driven first assignment.
 *    Original symptom of bd:python-factory-sopw.
 *
 * 2. Re-mount detach gap: dragging the inspector window or toggling
 *    its dock mode disconnects + reconnects the Lit custom element.
 *    `disconnectedCallback` calls `detachFromCore()` which clears the
 *    subscriber but does NOT clear `this._core`. On reconnect,
 *    `tryAutoAttachCore()` short-circuits because `attemptedAutoAttach`
 *    is true and `this._core` is non-null. React's wrapper passes the
 *    same `core` reference and `set core(value)` short-circuits on
 *    `oldValue === value`. Net: tabs go empty after every drag.
 *    bd:python-factory-sopw extension.
 *
 * 3. Icon-offscreen after open->close cycle: the SDK's
 *    `applyAnchorPosition('button')` computes a right-anchor offset
 *    against `window.innerWidth` and writes it as inline
 *    `transform: translate3d(...)` on the host. Our scaled wrapper
 *    `.copilot-status-host { transform: scale(0.45) }` (bd-r8o7,
 *    inspector.css) means the SDK's viewport math overshoots by ~2x
 *    and the icon ends up offscreen at e.g. x=1934 on a 1440px
 *    viewport. Verified by qa-tester (filed bd:python-factory-449j).
 *    Fix: in icon mode (`isOpen=false`), clear the SDK-written
 *    transform on the host so our parent's scale + natural layout
 *    positions the icon. Window mode is unaffected.
 *
 * Fix: a `MutationObserver` on `document.body` (subtree, childList).
 * Every time we observe a `<cpk-web-inspector>` enter the DOM OR notice
 * a tracked element whose `coreSubscriber` became null while still
 * connected, we force a fresh attach by toggling
 * `el.core = null; el.core = c`. The toggle works because the setter
 * short-circuit only applies to `oldValue === value`; null then same
 * is a real change.
 *
 * Source citations (`@copilotkitnext/[email protected]`
 * `dist/index.mjs`):
 *   - line 368  `set core(value)` short-circuits on identity match,
 *               then routes through detach/attach.
 *   - line 376  `attachToCore(core)` builds `coreSubscriber`, calls
 *               `core.subscribe(...)`, runs `processAgentsChanged`.
 *   - line 408  `detachFromCore()` clears `coreSubscriber` etc. but
 *               does NOT clear `this._core`.
 *   - line 470  `tryAutoAttachCore()` early-returns on prior attempt.
 *   - line 1014 `connectedCallback` invokes `tryAutoAttachCore`.
 *   - line 1024 `disconnectedCallback` invokes `detachFromCore`.
 *
 * Defensive: on initial mount we also validate the persisted button
 * position in `cpk:inspector:state`. If the user dragged the icon
 * offscreen and closed the window, the icon would be invisible on next
 * render. We drop just the offending `customPosition.button` key
 * (preserve other state like `dockMode`).
 *
 * Per dev-principles.md SDK-First "build it AND document the gap":
 * scoped to the bug surface, citations refresh-per-version-pin,
 * removable when upstream patches both lifecycle paths.
 */

import { useEffect } from "react";

const INSPECTOR_TAG = "cpk-web-inspector";
const STATE_STORAGE_KEY = "cpk:inspector:state";

interface InspectorElement extends HTMLElement {
  core?: unknown;
  coreSubscriber?: unknown;
  isOpen?: boolean;
}

/** Re-fire attachToCore by stashing then re-applying `el.core`. */
function reattachCore(el: InspectorElement): void {
  const core = el.core;
  if (!core) return;
  el.core = null;
  el.core = core;
}

/**
 * Bug #3 mitigation: in icon mode, clear the SDK's inline transform on
 * the host so our parent `.copilot-status-host { transform: scale(0.45) }`
 * controls layout. The SDK writes `translate3d(...)` based on
 * `window.innerWidth` math that doesn't see our scaled wrapper, pushing
 * the icon offscreen. We only clear in icon mode — window mode draws
 * floating/docked and needs the SDK's positioning.
 *
 * Idempotent: setting an empty transform when already empty is a no-op.
 */
function clearOffscreenIconTransform(el: InspectorElement): void {
  if (el.isOpen) return; // window mode — leave SDK positioning alone
  const current = el.style.transform;
  if (!current || current === "none") return;
  el.style.transform = "";
}

/**
 * Some elements may have been wired-up correctly by the SDK on first
 * mount. We only force a fresh attach when:
 *   - the element is freshly inserted (not in the WeakSet yet), or
 *   - we previously toggled it but its `coreSubscriber` is now null
 *     (= a `disconnectedCallback` ran detachFromCore).
 */
function ensureAttached(el: InspectorElement, seen: WeakSet<InspectorElement>): void {
  const fresh = !seen.has(el);
  const lostSubscriber = !el.coreSubscriber;
  if (fresh) {
    seen.add(el);
    reattachCore(el);
  } else if (lostSubscriber) {
    reattachCore(el);
  }
  // Bug #3 mitigation runs every sweep, regardless of attach state.
  // The SDK rewrites the inline transform on every isOpen toggle and
  // resize event — we override on every observed mutation.
  clearOffscreenIconTransform(el);
}

/** Drop a stored offscreen button position; keep other state intact. */
function pruneOffscreenIconPosition(): void {
  if (typeof window === "undefined") return;
  let stored: string | null;
  try {
    stored = window.localStorage.getItem(STATE_STORAGE_KEY);
  } catch {
    return;
  }
  if (!stored) return;
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(stored);
  } catch {
    return;
  }
  const cp = (parsed as { customPosition?: Record<string, { x?: number; y?: number }> })
    .customPosition;
  const btn = cp?.button;
  if (!btn) return;
  const { x, y } = btn;
  const offscreen =
    typeof x === "number" && typeof y === "number" &&
    (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight);
  if (!offscreen) return;
  delete cp.button;
  try {
    window.localStorage.setItem(STATE_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // best-effort
  }
}

export function InspectorAttachWorkaround() {
  useEffect(() => {
    if (typeof document === "undefined") return; // SSR guard

    pruneOffscreenIconPosition();

    const seen = new WeakSet<InspectorElement>();

    const sweep = () => {
      const elems = document.querySelectorAll(INSPECTOR_TAG);
      // `WebInspectorElement` (the SDK's declared element type) and
      // `InspectorElement` differ only by a private field, so TS refuses the
      // direct cast; the custom element is the same node either way.
      elems.forEach((el) => ensureAttached(el as unknown as InspectorElement, seen));
    };

    // Initial pass — the inspector may already be in the DOM by the
    // time this effect runs (React commits children top-down).
    sweep();

    // Watch for both child-list changes (re-mount) AND attribute mutations
    // (the SDK writes inline `style.transform` when toggling isOpen). Both
    // need to trigger our sweep so bug #3 stays mitigated across close.
    const observer = new MutationObserver(() => sweep());
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["style"],
    });

    return () => observer.disconnect();
  }, []);

  return null;
}
