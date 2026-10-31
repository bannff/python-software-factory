import type { CanvasViewId } from "@/lib/types";

/**
 * Canvas views that own a direct URL (deep-linkable). Every other view lives
 * at "/". Centralised so the activity bar and the ``fe_navigate_canvas``
 * frontend tool keep the address bar in sync the same way.
 */
export const ROUTED_VIEWS: Partial<Record<CanvasViewId, string>> = {
  capabilities: "/capabilities",
  artifacts: "/artifacts",
  crews: "/crews",
  sessions: "/sessions",
  schedules: "/schedules",
  lessons: "/lessons",
  settings: "/settings",
};

/** Push the address bar to match the target view (no-op if already correct). */
export function syncCanvasRoute(view: CanvasViewId): void {
  if (typeof window === "undefined") return;
  const target = ROUTED_VIEWS[view];
  if (target) {
    if (window.location.pathname !== target) window.history.pushState({}, "", target);
  } else if (window.location.pathname !== "/") {
    window.history.pushState({}, "", "/");
  }
}
