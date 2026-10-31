"use client";

/**
 * Host wiring for the ⌘K palette (bd:3jcls.4).
 *
 * Keeps `CommandPalette` prop-driven (and therefore unit-testable) while this
 * shim owns the one host dependency: the active canvas view, read from
 * `WorkbenchProvider` the same way `CanvasContextBridge` and
 * `CanvasSuggestions` do.
 *
 * Mounted inside `BridgeAdapterProvider` + `ActionTranscriptProvider` so
 * submissions route through the same `useAction` → `ui_dispatch_action` path
 * as agent-driven and A2UI-declared verbs, and land in the same transcript.
 */

import { CommandPalette } from "./command-palette";
import { useWorkbenchContext } from "@/lib/workbench-context";

export function CommandPaletteMount() {
  const { activeView } = useWorkbenchContext();
  return <CommandPalette activeView={activeView} />;
}
