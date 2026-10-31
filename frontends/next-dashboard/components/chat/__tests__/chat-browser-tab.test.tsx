import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ChatBrowserTab, normalizeUrl } from "../chat-browser-tab";

describe("normalizeUrl (row 26, feature-map)", () => {
  it("adds https:// to a bare host", () => {
    expect(normalizeUrl("example.com")).toBe("https://example.com/");
  });
  it("keeps an explicit scheme", () => {
    expect(normalizeUrl("http://example.com/x")).toBe("http://example.com/x");
  });
  it("returns null for blank input", () => {
    expect(normalizeUrl("   ")).toBeNull();
  });
});

describe("ChatBrowserTab (row 26, feature-map)", () => {
  it("loads a typed URL into the in-panel iframe", () => {
    render(<ChatBrowserTab />);
    fireEvent.change(screen.getByLabelText("Address bar"), { target: { value: "example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Go" }));
    const frame = screen.getByTitle("In-panel browser") as HTMLIFrameElement;
    expect(frame.getAttribute("src")).toBe("https://example.com/");
  });

  it("discloses that agent-driving and Annotate are not wired", () => {
    render(<ChatBrowserTab />);
    expect(screen.getByText(/agent cannot drive this browser/i)).toBeTruthy();
  });
});
