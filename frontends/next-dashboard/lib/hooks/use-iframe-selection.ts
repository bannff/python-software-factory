"use client";

import { useEffect } from "react";
import { parseSelectionMessage } from "@/lib/artifacts/iframe-selection";

/**
 * Row 65 (feature-map) — parent side of the sandboxed-artifact comment bridge.
 *
 * Listens for the `window` message the injected reporter posts from a
 * sandboxed `McpUiFrame` (widget/html/svg artifacts), validates it via
 * `parseSelectionMessage`, and hands the clean selection text to `onSelect`
 * (which opens the existing "Commenting on" anchor flow). Unrelated/malformed
 * messages are ignored by the validator. The remaining wiring is injecting
 * `selectionReporterScript()` into the frame's srcdoc.
 */
export function useIframeSelection(onSelect: (text: string) => void): void {
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      const selection = parseSelectionMessage(event.data);
      if (selection) onSelect(selection.text);
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [onSelect]);
}
