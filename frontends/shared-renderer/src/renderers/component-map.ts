import React from "react";
import {
  TypographyRenderer,
  ButtonRenderer,
  CardRenderer,
  MetricCardRenderer,
  TableRenderer,
  AlertRenderer,
  ProgressRenderer,
  FormRenderer,
  ListRenderer,
  ChartRenderer,
  ImageRenderer,
  TabsRenderer,
  BreadcrumbRenderer,
  DialogRenderer,
  ToastRenderer,
  PageRenderer,
  CodeRenderer,
  TimelineRenderer,
  TreeRenderer,
  CustomRenderer,
  SpacerRenderer,
  DividerRenderer,
  FallbackComponent,
  GraphViewerRenderer,
  ItemListRenderer,
  StatusDotRenderer,
  TrendBadgeRenderer,
  SparklineRenderer,
  DetailPanelRenderer,
  FilterBarRenderer,
  LineageRenderer,
  type ReactAdapterNode,
} from "./renderers";

type RendererComponent = React.ComponentType<{
  node: ReactAdapterNode;
  renderChildren: (children?: ReactAdapterNode[]) => React.ReactNode;
}>;

/**
 * Component-name → renderer registry.
 *
 * Entries are case- and underscore-insensitive at lookup time via
 * ``getRenderer`` and ``_norm`` (mirrors the BE allowlist normalization
 * in ``components/ui/src/factory/ui/mcp/paint_canvas.py``). Both
 * PascalCase (`Card`) and lower_snake (`item_list`) variants resolve
 * to the same renderer. Adding a new renderer = adding ONE entry under
 * its canonical key (PascalCase preferred); the normalizer handles the
 * casing variants for free.
 *
 * Covers the full A2UI ``COMPONENT_CATALOG`` (23 types) plus internal
 * brick aliases (`page`, `composed_page`, `hero`, `stat_grid`,
 * `live_feed`, `action_pane`, etc.) emitted by the Python ReactAdapter.
 *
 * bd:python-factory-3hkqx round 3 — meta-architect verdict
 * ``cec79d55-7ff3-41c0-b583-781bc5d7d2b7`` Q2(iv): single normalization
 * rule for type-set parity by construction.
 */
export const COMPONENT_MAP: Record<string, RendererComponent> = {
  // A2UI catalog — PascalCase canonical (matches COMPONENT_CATALOG).
  Alert: AlertRenderer,
  Button: ButtonRenderer,
  Card: CardRenderer,
  Chart: ChartRenderer,
  DatePicker: CustomRenderer,
  DetailPanel: DetailPanelRenderer,
  Divider: DividerRenderer,
  FilterBar: FilterBarRenderer,
  Form: FormRenderer,
  Image: ImageRenderer,
  ItemList: ItemListRenderer,
  List: ListRenderer,
  Lineage: LineageRenderer,
  Metric: MetricCardRenderer,
  Progress: ProgressRenderer,
  Select: CustomRenderer,
  Spacer: SpacerRenderer,
  Sparkline: SparklineRenderer,
  StatusDot: StatusDotRenderer,
  Table: TableRenderer,
  Text: TypographyRenderer,
  TextField: CustomRenderer,
  TimePicker: CustomRenderer,
  TrendBadge: TrendBadgeRenderer,

  // Internal brick aliases (raw view data) — kept for ReactAdapter output.
  Typography: TypographyRenderer,
  Tabs: TabsRenderer,
  Breadcrumb: BreadcrumbRenderer,
  Dialog: DialogRenderer,
  Toast: ToastRenderer,
  Page: PageRenderer,
  Code: CodeRenderer,
  Timeline: TimelineRenderer,
  Tree: TreeRenderer,
  Custom: CustomRenderer,
  page: PageRenderer,
  composed_page: PageRenderer,
  hero: CardRenderer,
  stat_grid: CardRenderer,
  live_feed: CardRenderer,
  action_pane: CardRenderer,
  modal: DialogRenderer,
  toast: ToastRenderer,
  code_block: CodeRenderer,
  tree_view: TreeRenderer,
  graph_viewer: GraphViewerRenderer,
  chat: CustomRenderer,
  breadcrumbs: BreadcrumbRenderer,
};

/**
 * Normalize a key for case+underscore-insensitive lookup. Mirrors the
 * BE rule in ``paint_canvas.py:_norm``.
 */
export function normalizeComponentName(s: string): string {
  return s.toLowerCase().replace(/_/g, "");
}

const _norm = normalizeComponentName;

const _NORMALIZED_MAP: Record<string, RendererComponent> = Object.fromEntries(
  Object.entries(COMPONENT_MAP).map(([k, v]) => [_norm(k), v]),
);

/**
 * Resolve a component name to its renderer with case+underscore-
 * insensitive lookup. Returns `null` if no renderer matches so the
 * caller can fall back to ``FallbackComponent`` and surface a helpful
 * error in the DOM.
 */
export function getRenderer(name: string | undefined): RendererComponent | null {
  if (!name) return null;
  return _NORMALIZED_MAP[_norm(name)] ?? null;
}

export { FallbackComponent };
export type { RendererComponent };
