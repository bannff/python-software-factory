import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ChannelRoom } from "../channel-room";
import type { ChannelParticipant } from "../channel-mentions";

const PARTICIPANTS: ChannelParticipant[] = [
  { id: "agent-ada", name: "Ada" },
  { id: "agent-bos", name: "Bos" },
];

const preview = () => screen.getByLabelText("Addressing preview").textContent;

describe("ChannelRoom (row 31, feature-map)", () => {
  it("renders participants and defaults addressing to everyone", () => {
    render(<ChannelRoom name="ops" participants={PARTICIPANTS} />);
    expect(screen.getByText("Ada")).toBeTruthy();
    expect(screen.getByText("Bos")).toBeTruthy();
    expect(preview()).toContain("Everyone");
  });

  it("narrows addressing to a mentioned participant", () => {
    render(<ChannelRoom participants={PARTICIPANTS} />);
    fireEvent.change(screen.getByLabelText("Channel composer"), { target: { value: "@ada ping" } });
    expect(preview()).toContain("Ada");
    expect(preview()).not.toContain("Bos");
  });

  it("discloses the deferred multi-agent fan-out", () => {
    render(<ChannelRoom participants={PARTICIPANTS} />);
    expect(screen.getByText(/multi-agent turn fan-out/i)).toBeTruthy();
  });
});
