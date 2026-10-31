import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ChatSideTab } from "../chat-side-tab";

describe("ChatSideTab (row 19, feature-map)", () => {
  it("records a scratch question and discloses the pending side-turn", () => {
    render(<ChatSideTab />);
    const input = screen.getByLabelText("Side chat input");
    fireEvent.change(input, { target: { value: "/btw what changed in logs" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(screen.getByText("what changed in logs")).toBeTruthy();
    expect(screen.getByText(/Answer pending/i)).toBeTruthy();
  });

  it("prefills from an Ask-about-this seed", () => {
    render(<ChatSideTab seed={'About this: "some span"'} />);
    expect(screen.getByLabelText("Side chat input")).toHaveProperty("value", 'About this: "some span"');
  });
});
