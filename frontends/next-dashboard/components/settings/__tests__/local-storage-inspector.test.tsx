import { describe, expect, it, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { LocalStorageInspector } from "../local-storage-inspector";

beforeEach(() => window.localStorage.clear());

describe("LocalStorageInspector (row 107, feature-map)", () => {
  it("lists stored keys with their values", () => {
    window.localStorage.setItem("theme", "dark");
    window.localStorage.setItem("companion-x-chat-width", "420");
    render(<LocalStorageInspector />);
    expect(screen.getByText("theme")).toBeTruthy();
    expect(screen.getByText("dark")).toBeTruthy();
    expect(screen.getByText("companion-x-chat-width")).toBeTruthy();
  });

  it("deletes a key and removes it from storage", () => {
    window.localStorage.setItem("scratch", "x");
    render(<LocalStorageInspector />);
    fireEvent.click(screen.getByRole("button", { name: "Delete scratch" }));
    expect(window.localStorage.getItem("scratch")).toBeNull();
    expect(screen.queryByText("scratch")).toBeNull();
  });

  it("shows an empty state with no keys", () => {
    render(<LocalStorageInspector />);
    expect(screen.getByText(/No keys stored/i)).toBeTruthy();
  });
});
