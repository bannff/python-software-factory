import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useEffect } from "react";
import { Refreshable } from "../refreshable";

function Probe({ onMount }: { onMount: () => void }) {
  useEffect(() => { onMount(); }, [onMount]);
  return <p>content</p>;
}

describe("Refreshable", () => {
  it("shows its content with a refresh control", () => {
    render(<Refreshable label="games"><p>content</p></Refreshable>);
    expect(screen.getByText("content")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Refresh games" })).toBeTruthy();
  });

  it("remounts the content on refresh so it refetches", () => {
    const onMount = vi.fn();
    render(<Refreshable label="games"><Probe onMount={onMount} /></Refreshable>);
    expect(onMount).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Refresh games" }));
    expect(onMount).toHaveBeenCalledTimes(2);
  });
});
