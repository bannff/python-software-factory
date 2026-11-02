import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatHeaderTitle } from "../chat-header-title";

describe("ChatHeaderTitle", () => {
  it("leads with an icon named Chat, not an uppercase text label", () => {
    render(<ChatHeaderTitle viewLabel="Graph" />);
    expect(screen.getByLabelText("Chat")).toBeTruthy();
    expect(screen.queryByText("Chat")).toBeNull();
    expect(screen.getByText("Graph")).toBeTruthy();
  });

  it("shows the live tool with a status dot only when one is running", () => {
    const { rerender } = render(<ChatHeaderTitle />);
    expect(screen.queryByTestId("live-tool")).toBeNull();
    rerender(<ChatHeaderTitle tool={{ label: "Read file", title: "read_file", connected: true }} />);
    expect(screen.getByTestId("live-tool").textContent).toBe("Read file");
  });
});
