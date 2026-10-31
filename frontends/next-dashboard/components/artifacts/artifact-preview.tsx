"use client";

import { McpUiFrame } from "@/components/chat/mcp-ui-frame";
import { selectionReporterScript } from "@/lib/artifacts/iframe-selection";
import { useIframeSelection } from "@/lib/hooks/use-iframe-selection";

export type ArtifactPreviewRecord = {
  slug: string;
  kind: "widget" | "html" | "markdown" | "svg" | "json" | "text";
  content: string;
};

const IFRAME_KINDS = new Set(["widget", "html", "svg"]);
const MAX_ANCHOR_CHARS = 4_000;
const NOOP = () => undefined;

export function ArtifactPreview({
  artifact, onAnchorSelect,
}: {
  artifact: ArtifactPreviewRecord;
  /** Fired with the selected text when the user finishes a selection in the
   * preview. DOM-rendered kinds (markdown/json/text) report via `mouseup`;
   * sandboxed kinds (widget/html/svg) report across the iframe boundary via
   * the row-65 postMessage bridge (`selectionReporterScript` injected into the
   * frame + `useIframeSelection` here), so anchored comments now work for
   * every kind. */
  onAnchorSelect?: (text: string) => void;
}) {
  // Row 65 bridge: receive selections posted up from the sandboxed frame.
  // Called unconditionally (hook rules); harmless for DOM kinds (no poster).
  useIframeSelection(onAnchorSelect ?? NOOP);

  if (IFRAME_KINDS.has(artifact.kind)) {
    const framed = `${artifact.content}\n<script>${selectionReporterScript()}</script>`;
    return (
      <div data-testid="artifact-sandbox-preview" className="[&>div]:m-0">
        <McpUiFrame
          uri={`artifact://${artifact.slug}`}
          mimeType="text/html"
          text={framed}
          serverLabel="Artifacts"
        />
      </div>
    );
  }
  const content = artifact.kind === "json"
    ? formatJson(artifact.content)
    : artifact.content;
  const handleMouseUp = () => {
    if (!onAnchorSelect) return;
    const text = window.getSelection()?.toString().trim() ?? "";
    if (text.length > 0 && text.length <= MAX_ANCHOR_CHARS) onAnchorSelect(text);
  };
  return (
    <pre
      data-testid="artifact-escaped-preview"
      onMouseUp={onAnchorSelect ? handleMouseUp : undefined}
      className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/50 bg-muted/20 p-4 text-xs text-foreground/85"
    >
      {content}
    </pre>
  );
}

function formatJson(content: string): string {
  try { return JSON.stringify(JSON.parse(content), null, 2); }
  catch { return content; }
}

export default ArtifactPreview;
