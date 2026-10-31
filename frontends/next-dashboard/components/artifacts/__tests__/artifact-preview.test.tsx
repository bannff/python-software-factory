import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ArtifactPreview } from "../artifact-preview";

vi.mock("framer-motion", () => ({ motion: new Proxy({}, { get: () => (p: React.PropsWithChildren<Record<string, unknown>>) => React.createElement("div", p, p.children) }) }));

const hostile = `<svg onload="parent.document.body.dataset.pwned='yes'"><script>document.cookie</script></svg>`;

describe("ArtifactPreview containment", () => {
  for (const kind of ["html", "widget", "svg"] as const) {
    it(`${kind} uses the exact sandboxed MCP UI iframe`, () => {
      render(<ArtifactPreview artifact={{ slug: `hostile-${kind}`, kind, content: hostile }} />);
      const iframe = document.querySelector("iframe");
      expect(iframe).not.toBeNull();
      expect(iframe?.getAttribute("sandbox")).toBe("allow-scripts");
      expect(iframe?.getAttribute("sandbox")).not.toContain("allow-same-origin");
      expect(iframe?.getAttribute("referrerpolicy")).toBe("no-referrer");
      expect(iframe?.getAttribute("srcdoc")).toContain("parent.document");
      expect(document.body.dataset.pwned).toBeUndefined();
    });
  }

  it("markdown remains escaped host text", () => {
    render(<ArtifactPreview artifact={{ slug: "notes", kind: "markdown", content: hostile }} />);
    expect(screen.getByTestId("artifact-escaped-preview").textContent).toContain("<svg");
    expect(document.querySelector("iframe")).toBeNull();
    expect(document.querySelector("svg")).toBeNull();
  });

  it("reports a text selection from the DOM-rendered preview via onAnchorSelect", () => {
    const onAnchorSelect = vi.fn();
    render(<ArtifactPreview
      artifact={{ slug: "notes", kind: "text", content: "hello world" }}
      onAnchorSelect={onAnchorSelect}
    />);
    const pre = screen.getByTestId("artifact-escaped-preview");
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "hello",
    } as unknown as Selection);
    fireEvent.mouseUp(pre);
    expect(onAnchorSelect).toHaveBeenCalledWith("hello");
  });

  it("does not fire onAnchorSelect for an empty/whitespace-only selection", () => {
    const onAnchorSelect = vi.fn();
    render(<ArtifactPreview
      artifact={{ slug: "notes", kind: "text", content: "hello world" }}
      onAnchorSelect={onAnchorSelect}
    />);
    const pre = screen.getByTestId("artifact-escaped-preview");
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "   ",
    } as unknown as Selection);
    fireEvent.mouseUp(pre);
    expect(onAnchorSelect).not.toHaveBeenCalled();
  });

  it("iframe-sandboxed kinds report selection across the bridge (row 65)", () => {
    const onAnchorSelect = vi.fn();
    render(<ArtifactPreview
      artifact={{ slug: "hostile-widget", kind: "widget", content: "<p>hi</p>" }}
      onAnchorSelect={onAnchorSelect}
    />);
    const iframe = document.querySelector("iframe");
    expect(iframe).not.toBeNull();
    // the reporter is injected into the sandboxed frame…
    expect(iframe?.getAttribute("srcdoc")).toContain("postMessage");
    // …and a selection posted up reaches the same onAnchorSelect DOM kinds use
    window.dispatchEvent(new MessageEvent("message", {
      data: { type: "artifact:selection", text: "  picked  span " },
    }));
    expect(onAnchorSelect).toHaveBeenCalledWith("picked span");
  });
});
