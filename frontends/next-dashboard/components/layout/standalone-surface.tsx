"use client";

import type { ReactNode } from "react";

/**
 * Chrome-less full-screen surface for the popout/embed routes (rows 125-130,
 * feature-map). The app's root layout always renders the workbench chrome
 * (Topbar/StatusBar/TerminalDock); an embed/popout window wants just the
 * surface, so this overlays the whole viewport (opaque, top layer) to cover
 * that chrome and present the wrapped view standalone. Scaffold: deeper
 * chrome-stripping (a dedicated route-group layout) is a later refinement —
 * this ships the standalone presentation over the existing components.
 */
export function StandaloneSurface({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <div aria-label={label ?? "Standalone surface"}
      className="fixed inset-0 z-[60] flex flex-col overflow-auto bg-background">
      {children}
    </div>
  );
}
