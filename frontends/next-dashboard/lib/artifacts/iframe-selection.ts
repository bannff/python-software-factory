/**
 * Row 65 (feature-map) — anchored artifact comments on sandboxed kinds.
 *
 * DOM-rendered kinds (markdown/json/text) already support select-text →
 * "Commenting on" anchored comments, but `widget`/`html`/`svg` render inside
 * a sandboxed iframe (`McpUiFrame`) whose selection the parent page cannot
 * read directly. This is the postMessage bridge protocol: a tiny reporter
 * script (injected into the sandbox) posts the user's selection up, and the
 * parent validates it here before opening the comment anchor.
 *
 * Pure protocol + validator — the McpUiFrame injection + the parent listener
 * hook that consume it are the wiring slice on top.
 */

export const ARTIFACT_SELECTION_MESSAGE = "artifact:selection";

export interface IframeSelection {
  text: string;
}

/**
 * Validate an inbound `message` event payload from a sandboxed artifact frame.
 * Returns the trimmed/normalised selection, or null when the payload is not a
 * well-formed selection message (so a hostile/unrelated postMessage is
 * ignored). Whitespace is collapsed and the anchor is capped at 1000 chars.
 */
export function parseSelectionMessage(data: unknown): IframeSelection | null {
  if (!data || typeof data !== "object") return null;
  const payload = data as Record<string, unknown>;
  if (payload.type !== ARTIFACT_SELECTION_MESSAGE) return null;
  const raw = typeof payload.text === "string" ? payload.text.replace(/\s+/g, " ").trim() : "";
  if (!raw) return null;
  return { text: raw.length > 1000 ? raw.slice(0, 1000) : raw };
}

/**
 * The reporter script injected into the sandboxed artifact iframe. On mouseup
 * it posts any non-empty selection up to the parent under the shared message
 * type. Kept as a single self-invoking string so it can be inlined into the
 * frame's srcdoc; the parent validates every message via
 * :func:`parseSelectionMessage`, so this side stays deliberately minimal.
 */
export function selectionReporterScript(): string {
  return (
    "(function(){function r(){var s=String(window.getSelection());" +
    "if(s&&s.trim()){parent.postMessage({type:" +
    JSON.stringify(ARTIFACT_SELECTION_MESSAGE) +
    ",text:s},'*');}}document.addEventListener('mouseup',r);})();"
  );
}
