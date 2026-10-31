"use client";

/**
 * <McpUiFrame> — UIResourceRenderer mount + sandbox override + onUIAction
 * bridge for carrier #5 (bd:python-factory-eyahj, EPIC python-factory-lo1g9).
 *
 * Replaces the lo1g9.3 <McpUiPlaceholder>. Mounts `<UIResourceRenderer>`
 * from `@mcp-ui/[email protected]` and applies security verdict
 * `d580bfdd-8928-47a4-8d73-a899328e128e`:
 *   (1) sandbox override drops `allow-same-origin` from SDK external_url
 *       default; (2) Zod + allowlist gate onUIAction; (3) CSP lives in
 *       `next.config.ts headers()`; (4) "External UI from <server>" chrome
 *       bar + Report; (5) 600px max-height, no fullscreen v1; (6) external_url
 *       origin allowlist UX in `mcp-ui-origin-allowlist.tsx`; (7) ErrorBoundary
 *       in `mcp-ui-error-boundary.tsx` mirrors <InlineView> (bd-lbvkh).
 *
 * Dispatcher pins (`@mcp-ui/[email protected]/dist/index.mjs`):
 *   :175 source-equality | :223 srcDoc allow-scripts | :234 src
 *   allow-scripts allow-same-origin (we override) | :2754 RemoteDOM
 *   allow-scripts + display:none | :2762-2774 mode dispatch by mimeType.
 */

import { UIResourceRenderer } from "@mcp-ui/client";
import type { UIActionResult } from "@mcp-ui/client";
import { motion } from "framer-motion";
import { ExternalLink, Flag } from "lucide-react";

import { McpUiErrorBoundary } from "./mcp-ui-error-boundary";
import {
  validateUIAction,
  classifyMimeType,
  normalizeMimeTypeForSDK,
} from "./mcp-ui-validator";
import type { ValidatedUIAction } from "./mcp-ui-validator";
import {
  OriginAllowlistGate,
  originFromUriList,
} from "./mcp-ui-origin-allowlist";

export interface McpUiFrameProps {
  /** mcp-ui resource fields preserved through MCP transport flattening. */
  uri: string;
  mimeType: string;
  /** HTML / URI-list / RemoteDOM source. */
  text?: string;
  /** Base64 fallback if the producer chose `blob` over `text`. */
  blob?: string;
  /** Server-friendly label for the chrome bar / Report button. */
  serverLabel?: string;
  /**
   * Forwarded to `onUIAction` after the validator passes. Caller
   * (chat host) is responsible for the actual tool dispatch / prompt
   * insertion / link navigation. The validator gates which actions
   * can ever reach this callback.
   */
  onAction?: (action: ValidatedUIAction) => Promise<unknown> | unknown;
}

/**
 * Renders the SDK + sandbox override. Used twice (gated and
 * un-gated) so we factor the renderer + chrome bar together.
 */
function FramedRenderer({
  uri,
  mimeType,
  text,
  blob,
  serverLabel,
  mode,
  onAction,
}: McpUiFrameProps & { mode: "rawHtml" | "externalUrl" | "remoteDom" }) {
  const handleAction = async (raw: UIActionResult): Promise<unknown> => {
    const validation = validateUIAction(raw);
    if (!validation.ok) {
      // eslint-disable-next-line no-console
      console.warn("[McpUiFrame] rejected onUIAction:", validation.reason);
      return { error: validation.reason };
    }
    if (onAction) return await onAction(validation.action);
    return undefined;
  };

  const reportClick = () => {
    // eslint-disable-next-line no-console
    console.warn("[McpUiFrame] user reported external UI", {
      uri,
      mimeType,
      serverLabel,
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="ml-11 my-2"
    >
      <div className="rounded-xl border border-border/50 bg-card/40 backdrop-blur-sm overflow-hidden shadow-sm">
        <div
          data-testid="mcp-ui-chrome-bar"
          className="flex items-center gap-2 border-b border-border/50 px-3 py-1.5"
        >
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-xs font-medium text-muted-foreground truncate">
            External UI from <code>{serverLabel}</code>
          </span>
          <span className="text-[10px] text-muted-foreground/70 ml-auto truncate max-w-[40%]">
            {mode}
          </span>
          <button
            type="button"
            data-testid="mcp-ui-report"
            aria-label="Report this UI"
            className="text-muted-foreground hover:text-destructive"
            onClick={reportClick}
          >
            <Flag className="h-3.5 w-3.5" />
          </button>
        </div>
        <div
          data-testid="mcp-ui-iframe-container"
          className="overflow-y-auto"
          style={{ maxHeight: "600px" }}
        >
          <McpUiErrorBoundary resetKey={uri}>
            <UIResourceRenderer
              // SDK types resource: Partial<Resource> (bare MCP shape, no
              // text/blob) but runtime reads them at index.mjs:60-100.
              // mimeType normalize: SDK strict-equality at :21-22 rejects
              // RFC 7231 params on text/html / text/uri-list. RemoteDOM
              // keeps params (framework=react is read).
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              resource={{ uri, mimeType: normalizeMimeTypeForSDK(mimeType), text, blob } as any}
              onUIAction={handleAction}
              // Verdict d580bfdd §1: drop allow-same-origin from SDK
              // external_url default (index.mjs:234). Pass same value for
              // srcDoc/remoteDom (already SDK default at :223 + :2754) so
              // a regression can't silently widen. SDK types iframeProps
              // against HTMLAttributes which omits `sandbox`; cast around
              // the upstream typing bug.
              htmlProps={{
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                iframeProps: { sandbox: "allow-scripts", referrerPolicy: "no-referrer" } as any,
              }}
            />
          </McpUiErrorBoundary>
        </div>
      </div>
    </motion.div>
  );
}

export function McpUiFrame(props: McpUiFrameProps) {
  const { mimeType, text, serverLabel = "external" } = props;
  const mode = classifyMimeType(mimeType);

  if (!mode) {
    return (
      <div
        data-testid="mcp-ui-error"
        role="alert"
        className="ml-11 my-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm"
      >
        Unsupported mcp-ui mimeType: <code>{mimeType}</code>
      </div>
    );
  }

  if (mode === "externalUrl") {
    const origin = originFromUriList(text ?? "");
    if (!origin) {
      return (
        <div
          data-testid="mcp-ui-error"
          role="alert"
          className="ml-11 my-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm"
        >
          External URL resource carries no parseable URI.
        </div>
      );
    }
    return (
      <OriginAllowlistGate origin={origin} serverLabel={serverLabel}>
        <FramedRenderer {...props} mode={mode} />
      </OriginAllowlistGate>
    );
  }

  return <FramedRenderer {...props} mode={mode} />;
}
