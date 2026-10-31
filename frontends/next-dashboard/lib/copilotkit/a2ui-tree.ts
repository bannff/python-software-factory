/**
 * A2UI flat → ReactAdapterNode tree translator.
 *
 * Carved out of ``a2ui-canvas-slots.ts`` to keep that module under the
 * 200 LOC tenet. Used by ``usePaintedComponents`` (carrier #2 canvas
 * paint) — but pure, no React deps, so unit-testable on its own.
 *
 * Three child-shape variants accepted in one pass:
 *   1. Top-level ``children`` — already a tree, recurse in place.
 *   2. Flat siblings with ``parent: "<id>"`` — canonical A2UI; resolve
 *      via id index, append to parent's ``children``, drop from top.
 *   3. ``props.children: [...]`` — LLM-natural shape, lifted to
 *      ``parent:`` refs. The BE producer (``ui_paint_canvas``)
 *      normalizes this to (2) before wire emit, but we handle for
 *      legacy / non-canvas-paint A2UI sources.
 *
 * SDK gap: Strands/CopilotKit/AG-UI all absent on
 * A2UI→ReactAdapterNode. We own this. bd:python-factory-3hkqx round 3,
 * meta-architect verdict ``cec79d55-7ff3-41c0-b583-781bc5d7d2b7`` Q3.
 */

import type { ReactAdapterNode } from "@companion-x/shared-renderer";

interface A2UIWireComponent {
  id?: string;
  type?: string;
  component?: string;
  originalType?: string;
  parent?: string;
  props?: Record<string, unknown>;
  children?: A2UIWireComponent[];
}

interface AdapterWithRef {
  adapter: ReactAdapterNode;
  parentRef?: string;
}

interface ToAdapterResult {
  adapter: ReactAdapterNode;
  lifted: ReactAdapterNode[];
  parentRef?: string;
}

function _toAdapter(
  c: A2UIWireComponent,
  inheritedParent?: string,
): ToAdapterResult {
  const props = c.props ?? {};
  let cleanProps: Record<string, unknown> = props;
  let propChildren: A2UIWireComponent[] = [];
  if (Array.isArray((props as { children?: unknown[] }).children)) {
    const { children: kids, ...rest } = props as {
      children: A2UIWireComponent[];
    } & Record<string, unknown>;
    propChildren = kids;
    cleanProps = rest;
  }
  const topChildren = Array.isArray(c.children) ? c.children : [];
  const childResults = [...topChildren, ...propChildren].map((kid) =>
    _toAdapter(kid, c.id),
  );
  const adapter: ReactAdapterNode = {
    id: c.id ?? "",
    component: c.component ?? c.type ?? "",
    originalType: c.originalType ?? c.type ?? c.component ?? "",
    props: cleanProps,
    children:
      childResults.length > 0 ? childResults.map((r) => r.adapter) : undefined,
  };
  const lifted = childResults.flatMap((r) => r.lifted);
  return { adapter, lifted, parentRef: c.parent ?? inheritedParent };
}

/**
 * Translate an A2UI flat payload into a ReactAdapterNode tree.
 *
 * Drops orphan ``parent:`` refs (parent id not found) at the top level
 * so render still proceeds. Always writes ``component`` and
 * ``originalType`` so the renderer's lookup + fallback strings work.
 */
export function a2uiToReactAdapterNodes(
  components: unknown[],
): ReactAdapterNode[] {
  if (!Array.isArray(components) || components.length === 0) return [];
  const top = (components as A2UIWireComponent[]).map((c) => _toAdapter(c));
  const allWithRefs: AdapterWithRef[] = [
    ...top.map((r) => ({ adapter: r.adapter, parentRef: r.parentRef })),
    ...top.flatMap((r) =>
      r.lifted.map((a) => ({ adapter: a, parentRef: undefined })),
    ),
  ];

  const byId: Record<string, ReactAdapterNode> = {};
  for (const { adapter } of allWithRefs) {
    if (adapter.id) byId[adapter.id] = adapter;
  }

  const roots: ReactAdapterNode[] = [];
  for (const { adapter, parentRef } of allWithRefs) {
    if (
      typeof parentRef === "string" &&
      parentRef.length > 0 &&
      byId[parentRef]
    ) {
      const parent = byId[parentRef];
      if (!parent.children) parent.children = [];
      if (!parent.children.includes(adapter)) parent.children.push(adapter);
      continue;
    }
    roots.push(adapter);
  }
  return roots;
}
