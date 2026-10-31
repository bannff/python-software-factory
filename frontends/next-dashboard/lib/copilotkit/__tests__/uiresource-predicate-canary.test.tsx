/**
 * Wildcard UIResource predicate canary
 * (bd:python-factory-r6kki, EPIC python-factory-lo1g9).
 *
 * Pins the carrier-discriminating logic the wildcard
 * `<WildcardRender>` runs on every tool result. Mirrors the
 * dispatcher-canary / state-delta-canary precedent: the test asserts
 * which BRANCH fires for each canonical payload shape so a future
 * refactor that reorders the predicate or drops a flow is caught at
 * CI time.
 *
 * Source pins (dev-principles.md "dispatcher source rule"):
 *   - First-wildcard-find:
 *     `@copilotkitnext/[email protected]/dist/hooks/use-render-tool-call.mjs:58`.
 *     Justifies multiplexing INSIDE one render function — a second
 *     `useDefaultRenderTool` call would be dead.
 *   - Wildcard registration overwrite-by-key:
 *     `@copilotkitnext/[email protected]/dist/hooks/use-render-tool.mjs:71-72`.
 *     Justifies the "single dispatcher" constraint — repeat
 *     registrations clobber, no stacking.
 *   - mcp-ui consumer (lands lo1g9.4):
 *     `@mcp-ui/[email protected]/dist/components/UIResourceRenderer.{tsx,js}`.
 *
 * Verdicts:
 *   - meta-architect `26d6cd24-b165-4481-96ee-6a010277f22d` (Option A
 *     multiplex inside one wildcard, mcp-ui first ordering)
 *   - security-engineer `d580bfdd-8928-47a4-8d73-a899328e128e`
 *     (postMessage validator policy — applies in lo1g9.4)
 *   - strands-expert `293c185e-4d29-4728-b6e7-eee04d633ff3`
 *     (single-fall-through dispatcher constraint)
 */

import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import * as React from "react";
import {
  WildcardRender,
  detectCarrier,
} from "@/lib/copilotkit/tool-renderers";

const TOOL_NAME = "any_tool";

function renderWildcard(parsed: unknown) {
  return render(
    <WildcardRender
      name={TOOL_NAME}
      status="complete"
      parameters={{}}
      parsed={parsed}
    />,
  );
}

describe("wildcard UIResource predicate canary (bd:python-factory-r6kki)", () => {
  it("Case 1 — mcp-ui nested (Flow A) routes to <McpUiFrame> chrome bar", () => {
    // Producer side: first-party FastMCP / GitHub MCP server emits an
    // MCP `EmbeddedResource` content block. When the chat surface
    // sees the JSON-stringified result, it parses the canonical
    // nested shape `{type:"resource", resource:{uri:"ui://...",
    // mimeType, text|blob}}`.
    const payload = {
      type: "resource",
      resource: {
        uri: "ui://factory/foo",
        mimeType: "text/html;profile=mcp-app",
        text: "<div>hi</div>",
      },
    };

    expect(detectCarrier(payload)).toBe("mcp-ui");

    const { getByTestId, queryByTestId, container } = renderWildcard(payload);
    // Carrier #5 mounts <McpUiFrame> which renders an "External UI
    // from <server>" chrome bar — matches the SDK iframe parent so
    // even a snapshot test does not need to render the iframe to
    // confirm the predicate routed correctly.
    expect(getByTestId("mcp-ui-chrome-bar")).toBeTruthy();
    // Carrier #1 (InlineView) must NOT fire on the same payload.
    expect(queryByTestId("inline-view")).toBeNull();
    expect(container.querySelector(".lucide-layout-grid")).toBeNull();
  });

  it("Case 2 — mcp-ui flat (Flow B) routes to <McpUiFrame> chrome bar", () => {
    // Producer side: Strands MCPClient flattens `EmbeddedResource`
    // by default. `FactoryMCPClient` (bd:python-factory-nmzlk,
    // `components/agent/src/factory/agent/runtime/adapters/strands_mcp_client_factory.py:114-178`)
    // preserves uri+mimeType so the dispatcher still sees enough to
    // route. THIS is the upstream-MCP-server compatibility lane.
    const payload = {
      text: "<div>hello</div>",
      uri: "ui://github/issue/123",
      mimeType: "text/html;profile=mcp-app",
    };

    expect(detectCarrier(payload)).toBe("mcp-ui");

    const { getByTestId } = renderWildcard(payload);
    expect(getByTestId("mcp-ui-chrome-bar")).toBeTruthy();
  });

  it("Case 3 — A2UI components payload routes to InlineView (carrier #1)", () => {
    const payload = {
      components: [
        { id: "c1", type: "Card", props: { title: "Inline-Card-Title" } },
      ],
      name: "InlineViewHeader",
    };

    expect(detectCarrier(payload)).toBe("a2ui");

    const { container, queryByTestId } = renderWildcard(payload);
    // Carrier #1's InlineView renders the payload `name` in its
    // header and pipes the `components` tree through ComponentTree →
    // CardRenderer.
    expect(container.textContent).toContain("InlineViewHeader");
    expect(container.textContent).toContain("Inline-Card-Title");
    expect(queryByTestId("mcp-ui-chrome-bar")).toBeNull();
  });

  it("Case 4 — plain tool result (no carrier shape) renders the bare ToolCallCard", () => {
    const payload = { result: "ok" };

    expect(detectCarrier(payload)).toBe("plain");

    const { queryByTestId, container } = renderWildcard(payload);
    expect(queryByTestId("mcp-ui-chrome-bar")).toBeNull();
    // The ToolCallCard chrome renders the tool name in its header.
    expect(container.textContent).toContain(TOOL_NAME);
  });

  it("Case 5 — predicate ordering: payload with BOTH components AND a ui:// resource routes to mcp-ui", () => {
    // Defensive: an upstream producer that accidentally bundles both
    // an `Array.isArray(components)` field and a `resource.uri`
    // ui-scheme MUST land on the more-specific (mcp-ui) branch.
    // This is the meta-architect ordering pin
    // (`26d6cd24-b165-4481-96ee-6a010277f22d`): mcp-ui first, A2UI
    // second.
    const payload = {
      type: "resource",
      resource: {
        uri: "ui://factory/widget",
        mimeType: "text/html;profile=mcp-app",
        text: "<div/>",
      },
      components: [
        { id: "c1", type: "Card", props: {} },
      ],
    };

    expect(detectCarrier(payload)).toBe("mcp-ui");

    const { getByTestId } = renderWildcard(payload);
    expect(getByTestId("mcp-ui-chrome-bar")).toBeTruthy();
  });

  it("Case 6 — uri without `ui://` scheme is NOT mcp-ui (falls through to plain card)", () => {
    // Security pin tied to the security-engineer verdict
    // `d580bfdd-8928-47a4-8d73-a899328e128e`: only `ui://`-scheme URIs
    // are eligible for the iframe sandbox renderer in lo1g9.4. An
    // attacker-controlled producer that smuggles a remote URL
    // through the same shape MUST be ignored by the predicate — it
    // is not routed to a UIResource consumer.
    const payload = {
      uri: "https://evil.example/",
      mimeType: "text/html",
      text: "<script>x</script>",
    };

    expect(detectCarrier(payload)).toBe("plain");

    const { queryByTestId } = renderWildcard(payload);
    expect(queryByTestId("mcp-ui-chrome-bar")).toBeNull();
  });
});
