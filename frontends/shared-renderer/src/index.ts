/**
 * @companion-x/shared-renderer — framework-agnostic A2UI component
 * renderer extracted from next-dashboard (Track 6, bd:python-factory-ons71).
 *
 * Consumed by the Next dashboard (NextBridgeAdapter). Hosts supply MCP data
 * through a single {@link BridgeAdapter} mounted via {@link BridgeAdapterProvider}.
 */

// Renderer surface (names preserved from the in-tree renderer/index.ts).
export { ComponentRenderer, ComponentTree } from "./renderers/component-renderer";
export { COMPONENT_MAP, getRenderer } from "./renderers/component-map";
export { AnimationWrapper } from "./renderers/animation-wrapper";
export { LineageRenderer, normalizeLineageData } from "./renderers/renderers-lineage";
export type { ReactAdapterNode, RendererProps } from "./renderers/renderer-types";

// Data seam (new in Track 6).
export { unwrapToolResult } from "./tool-result";
export { useToolData } from "./renderers/use-tool-data";
export type { BridgeAdapter } from "./bridge-adapter";
export { BridgeAdapterProvider, useBridge, useBridgeOptional } from "./bridge-adapter-context";

// Action seam (bd:python-factory-3jcls.3 / bd:python-factory-372an).
// Every human-fired verb goes through `useAction` → `ui_dispatch_action`.
export { useAction } from "./actions/use-action";
export type { ActionState, UseActionResult } from "./actions/use-action";
export {
  DISPATCH_TOOL, asActionRef, dedupeKey, gestureId, resolveArgs, resolveBinding,
} from "./actions/action-ref";
export type { ActionRef, DispatchOutcome } from "./actions/action-ref";
export {
  InvalidationProvider, useInvalidation, useRegisterRefetch,
} from "./actions/invalidation-context";
export { TranscriptSinkProvider, useTranscriptSink } from "./actions/transcript-context";
export type { TranscriptEntry, TranscriptSink } from "./actions/transcript-context";
