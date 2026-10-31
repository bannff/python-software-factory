import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { ChannelsPage, type Channel } from "../channels-page";

const CHANNELS: Channel[] = [
  { id: "ops", name: "ops", participants: [{ id: "a", name: "Ada" }] },
  { id: "sec", name: "sec", participants: [{ id: "b", name: "Bos" }] },
];

describe("ChannelsPage (row 31, feature-map)", () => {
  it("shows an honest empty state when no channels are supplied", () => {
    render(<ChannelsPage channels={[]} />);
    expect(screen.getByText(/rooms\/membership backend .* not wired/i)).toBeTruthy();
  });

  it("selects the first channel and switches rooms on click", () => {
    render(<ChannelsPage channels={CHANNELS} />);
    // first channel's room + participant shown by default
    expect(screen.getByLabelText("Channel room").textContent).toContain("Ada");
    const list = within(screen.getByLabelText("Channel list"));
    fireEvent.click(list.getByRole("button", { name: /sec/ }));
    expect(screen.getByLabelText("Channel room").textContent).toContain("Bos");
  });
});
