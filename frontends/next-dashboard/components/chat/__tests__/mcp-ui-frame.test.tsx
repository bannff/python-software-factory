/**
 * <McpUiFrame> contract test (bd:python-factory-eyahj — EPIC
 * python-factory-lo1g9). Pins the security policy from verdict
 * `d580bfdd-8928-47a4-8d73-a899328e128e`:
 *
 *   1. Sandbox attrs are EXACTLY `allow-scripts` (no
 *      `allow-same-origin`) for ALL three modes — pinned via
 *      snapshot of the rendered iframe.
 *   2. postMessage validator: rejects events whose tool / intent is
 *      not in the allowlist, fails Zod shape, etc.
 *   3. ErrorBoundary catches throws inside `<UIResourceRenderer>`.
 *   4. "External UI from <server>" chrome bar renders.
 *   5. Origin allowlist modal renders for new external_url origins;
 *      persists the "always allow" decision.
 *
 * The sandbox snapshots assert the SDK actually renders an iframe
 * with the right attribute. Future @mcp-ui/client SDK regressions
 * that widen the default sandbox attribute (e.g. by accidentally
 * shipping `allow-same-origin` everywhere) will fail this test.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

import { McpUiFrame } from "../mcp-ui-frame";
import {
  validateUIAction,
  classifyMimeType,
  ALLOWED_IFRAME_TOOLS,
  ALLOWED_IFRAME_INTENTS,
} from "../mcp-ui-validator";
import { rememberOriginAlways } from "../mcp-ui-origin-allowlist";

vi.mock("framer-motion", () => ({
  motion: new Proxy(
    {},
    {
      get:
        () =>
          ({
            children,
            ...rest
          }: React.PropsWithChildren<Record<string, unknown>>) =>
            React.createElement("div", rest, children),
    },
  ),
}));

beforeEach(() => {
  if (typeof window !== "undefined") {
    window.localStorage.clear();
  }
});

/* ------------------------------------------------------------------ */
/*  validator                                                          */
/* ------------------------------------------------------------------ */

describe("validateUIAction — postMessage 5-step pipeline (steps 3-4)", () => {
  it("accepts a tool call with an allowlisted toolName", () => {
    expect(ALLOWED_IFRAME_TOOLS).toContain("graph_get_app_topology");
    const result = validateUIAction({
      type: "tool",
      payload: { toolName: "graph_get_app_topology", params: { id: "x" } },
    });
    expect(result.ok).toBe(true);
  });

  it("rejects a tool call with a non-allowlisted toolName", () => {
    const result = validateUIAction({
      type: "tool",
      payload: { toolName: "memory_store", params: {} },
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toMatch(/tool-not-allowlisted/);
    }
  });

  it("rejects @authoring / @operational tool routes (security-engineer §4)", () => {
    // Spot-check a handful of mutating tool names that MUST never
    // be reachable from the iframe.
    const forbidden = [
      "ui_paint_chat",
      "graph_add_entity",
      "memory_store",
      "agent_invoke_graph",
      "agent_launch_swarm",
    ];
    for (const t of forbidden) {
      const result = validateUIAction({
        type: "tool",
        payload: { toolName: t, params: {} },
      });
      expect(result.ok, `${t} should be rejected`).toBe(false);
    }
  });

  it("accepts an allowlisted intent and rejects an arbitrary one", () => {
    expect(ALLOWED_IFRAME_INTENTS).toContain("navigate-canvas");
    const ok = validateUIAction({
      type: "intent",
      payload: { intent: "navigate-canvas", params: { tab: "graph" } },
    });
    expect(ok.ok).toBe(true);

    const bad = validateUIAction({
      type: "intent",
      payload: { intent: "exfiltrate", params: {} },
    });
    expect(bad.ok).toBe(false);
  });

  it("rejects raw events that fail the Zod discriminatedUnion shape", () => {
    const result = validateUIAction({ type: "tool", payload: "bogus" });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toMatch(/zod-shape/);
    }
  });

  it("rejects unknown action types", () => {
    const result = validateUIAction({ type: "exfil", payload: {} });
    expect(result.ok).toBe(false);
  });
});

describe("classifyMimeType — mode dispatch (mirrors SDK Rt())", () => {
  it("normalizes RFC 7231 parameters", () => {
    expect(classifyMimeType("text/html;profile=mcp-app")).toBe("rawHtml");
    expect(classifyMimeType("text/html")).toBe("rawHtml");
    expect(classifyMimeType("text/uri-list")).toBe("externalUrl");
    expect(
      classifyMimeType("application/vnd.mcp-ui.remote-dom+javascript"),
    ).toBe("remoteDom");
    expect(classifyMimeType("text/plain")).toBeNull();
  });
});

/* ------------------------------------------------------------------ */
/*  Rendered iframe — sandbox attrs (security verdict §1)              */
/* ------------------------------------------------------------------ */

function getIframe(): HTMLIFrameElement | null {
  return document.querySelector("iframe");
}

function getSandboxTokens(iframe: HTMLIFrameElement | null): string[] {
  if (!iframe) return [];
  const raw = iframe.getAttribute("sandbox") ?? "";
  return raw.split(/\s+/).filter(Boolean).sort();
}

const FORBIDDEN_SANDBOX = [
  "allow-same-origin",
  "allow-top-navigation",
  "allow-popups",
  "allow-popups-to-escape-sandbox",
  "allow-modals",
  "allow-forms",
  "allow-downloads",
  "allow-presentation",
  "allow-pointer-lock",
  "allow-orientation-lock",
  "allow-storage-access-by-user-activation",
];

describe("<McpUiFrame> sandbox attribute snapshot (security verdict §1)", () => {
  it("inline_html mode (text/html) renders sandbox=\"allow-scripts\" ONLY", () => {
    render(
      <McpUiFrame
        uri="ui://factory/inline"
        mimeType="text/html;profile=mcp-app"
        text="<div>hello</div>"
        serverLabel="factory"
      />,
    );
    const iframe = getIframe();
    expect(iframe).not.toBeNull();
    expect(getSandboxTokens(iframe)).toEqual(["allow-scripts"]);
    for (const f of FORBIDDEN_SANDBOX) {
      expect(getSandboxTokens(iframe)).not.toContain(f);
    }
  });

  it("external_url mode (text/uri-list) renders sandbox=\"allow-scripts\" — drops SDK default allow-same-origin", () => {
    // Pre-allow the origin so the gate skips the modal and the
    // iframe actually mounts.
    rememberOriginAlways("https://example.com");

    render(
      <McpUiFrame
        uri="ui://factory/external"
        mimeType="text/uri-list"
        text="https://example.com/widget"
        serverLabel="factory"
      />,
    );
    const iframe = getIframe();
    expect(iframe).not.toBeNull();
    // This is the security-critical assertion: the SDK default
    // (`@mcp-ui/[email protected]/dist/index.mjs:234`) is
    // `allow-scripts allow-same-origin`. We override via
    // `htmlProps.iframeProps.sandbox` and the DOM must reflect it.
    expect(getSandboxTokens(iframe)).toEqual(["allow-scripts"]);
    for (const f of FORBIDDEN_SANDBOX) {
      expect(getSandboxTokens(iframe)).not.toContain(f);
    }
    expect(iframe?.getAttribute("referrerpolicy")).toBe("no-referrer");
  });

  it("remote_dom mode renders sandbox=\"allow-scripts\" with display:none", () => {
    render(
      <McpUiFrame
        uri="ui://factory/remote"
        mimeType="application/vnd.mcp-ui.remote-dom+javascript"
        text="// noop"
        serverLabel="factory"
      />,
    );
    const iframe = getIframe();
    expect(iframe).not.toBeNull();
    expect(getSandboxTokens(iframe)).toEqual(["allow-scripts"]);
    // SDK pins display:none for remoteDom — verifies we don't
    // accidentally widen.
    expect(iframe?.style.display).toBe("none");
  });
});

/* ------------------------------------------------------------------ */
/*  Chrome bar + ErrorBoundary + unsupported mime                     */
/* ------------------------------------------------------------------ */

describe("<McpUiFrame> chrome bar + error states", () => {
  it("renders the 'External UI from <server>' chrome bar with Report", () => {
    render(
      <McpUiFrame
        uri="ui://factory/inline"
        mimeType="text/html"
        text="<div/>"
        serverLabel="github_search"
      />,
    );
    const bar = screen.getByTestId("mcp-ui-chrome-bar");
    expect(bar.textContent).toMatch(/External UI from/);
    expect(bar.textContent).toMatch(/github_search/);
    expect(screen.getByTestId("mcp-ui-report")).toBeTruthy();
  });

  it("clamps the iframe container to 600px max-height (verdict §5)", () => {
    render(
      <McpUiFrame
        uri="ui://factory/inline"
        mimeType="text/html"
        text="<div/>"
      />,
    );
    const container = screen.getByTestId("mcp-ui-iframe-container");
    expect(container.style.maxHeight).toBe("600px");
    expect(container.className).toMatch(/overflow-y-auto/);
  });

  it("renders an inline error card for an unsupported mimeType", () => {
    render(
      <McpUiFrame
        uri="ui://factory/x"
        mimeType="text/plain"
        text="hello"
      />,
    );
    expect(screen.getByTestId("mcp-ui-error").textContent).toMatch(
      /Unsupported mcp-ui mimeType/,
    );
  });

  it("renders an error card for external_url with unparseable text", () => {
    render(
      <McpUiFrame
        uri="ui://factory/external"
        mimeType="text/uri-list"
        text="not-a-url"
      />,
    );
    // originFromUriList returns null → error card.
    expect(screen.getByTestId("mcp-ui-error").textContent).toMatch(
      /no parseable URI/,
    );
  });
});

/* ------------------------------------------------------------------ */
/*  Origin allowlist UX (verdict §6)                                  */
/* ------------------------------------------------------------------ */

describe("<McpUiFrame> origin allowlist UX (verdict §6)", () => {
  it("shows the confirm card for a new external_url origin", () => {
    render(
      <McpUiFrame
        uri="ui://factory/ext"
        mimeType="text/uri-list"
        text="https://new-origin.example/x"
      />,
    );
    const confirm = screen.getByTestId("mcp-ui-origin-confirm");
    expect(confirm.textContent).toMatch(/https:\/\/new-origin\.example/);
    // The renderer iframe is gated behind the allowlist — it should
    // NOT mount until the user picks a decision.
    expect(getIframe()).toBeNull();
  });

  it("renders directly for a previously persisted origin", () => {
    rememberOriginAlways("https://trusted.example");

    render(
      <McpUiFrame
        uri="ui://factory/ext"
        mimeType="text/uri-list"
        text="https://trusted.example/widget"
      />,
    );

    expect(screen.queryByTestId("mcp-ui-origin-confirm")).toBeNull();
    expect(getIframe()).not.toBeNull();
  });

  it("'Always allow this origin' persists the decision and mounts the iframe", () => {
    render(
      <McpUiFrame
        uri="ui://factory/ext"
        mimeType="text/uri-list"
        text="https://persist.example/widget"
      />,
    );
    const confirm = screen.getByTestId("mcp-ui-origin-confirm");
    expect(confirm).toBeTruthy();
    expect(getIframe()).toBeNull();

    act(() => {
      fireEvent.click(screen.getByText(/Always allow this origin/));
    });

    expect(screen.queryByTestId("mcp-ui-origin-confirm")).toBeNull();
    expect(getIframe()).not.toBeNull();

    const stored = window.localStorage.getItem("mcp-ui:origin-allowlist:v1");
    expect(stored).toContain("https://persist.example");
  });

  it("'Allow this thread' mounts the iframe but does NOT persist", () => {
    render(
      <McpUiFrame
        uri="ui://factory/ext"
        mimeType="text/uri-list"
        text="https://thread.example/widget"
      />,
    );
    expect(screen.getByTestId("mcp-ui-origin-confirm")).toBeTruthy();

    act(() => {
      fireEvent.click(screen.getByText(/Allow this thread/));
    });

    expect(getIframe()).not.toBeNull();
    expect(window.localStorage.getItem("mcp-ui:origin-allowlist:v1")).toBeNull();
  });

  it("'Never' blocks the iframe", () => {
    render(
      <McpUiFrame
        uri="ui://factory/ext"
        mimeType="text/uri-list"
        text="https://blocked.example/widget"
      />,
    );

    act(() => {
      fireEvent.click(screen.getByText(/Never/));
    });

    expect(screen.getByTestId("mcp-ui-origin-blocked")).toBeTruthy();
    expect(getIframe()).toBeNull();
  });
});

/* ------------------------------------------------------------------ */
/*  ErrorBoundary (verdict §7 + bd-lbvkh mirror)                      */
/* ------------------------------------------------------------------ */

describe("<McpUiFrame> ErrorBoundary (mirrors bd:python-factory-lbvkh)", () => {
  it("inline_html with invalid blob lands the user on the iframe error path", () => {
    // The SDK's `He()` decode logic
    // (`@mcp-ui/[email protected]/dist/index.mjs:60-100`) returns an
    // `{error}` object for malformed blobs and the renderer
    // surfaces it as a `text-orange-500` paragraph rather than
    // throwing. The ErrorBoundary case below covers true throws;
    // this test pins the SDK error-text path so a regression where
    // blob decode starts raising would still land the user on a
    // rendered error UI rather than a blank panel.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <McpUiFrame
        uri="ui://factory/x"
        mimeType="text/html"
        blob="!!!not-base64!!!"
      />,
    );
    // SDK error text or our boundary card — either way the user
    // sees a visible failure, not a blank panel.
    const errorEl =
      screen.queryByTestId("mcp-ui-error") ??
      document.querySelector(".text-orange-500, .text-red-500");
    expect(errorEl).not.toBeNull();
    errSpy.mockRestore();
  });

  it("our boundary catches synthetic React throws below <UIResourceRenderer>", () => {
    // Pin the boundary-reset behavior directly via the boundary
    // class itself (mirrors bd-lbvkh), independent of SDK
    // internals so a future SDK behavior change can't silently
    // mask the boundary's contract.
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const Boom = (): React.ReactElement => {
      throw new Error("synthetic throw");
    };

    return import("../mcp-ui-error-boundary").then(({ McpUiErrorBoundary }) => {
      render(
        <McpUiErrorBoundary resetKey="k1">
          <Boom />
        </McpUiErrorBoundary>,
      );
      expect(screen.getByTestId("mcp-ui-error").textContent).toMatch(
        /External UI failed to render/,
      );
      expect(screen.getByTestId("mcp-ui-error").textContent).toMatch(
        /synthetic throw/,
      );
      errSpy.mockRestore();
    });
  });
});
