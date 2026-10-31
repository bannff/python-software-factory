import { describe, expect, it } from "vitest";
import { parseChannelMentions, type ChannelParticipant } from "../channel-mentions";

const PARTICIPANTS: ChannelParticipant[] = [
  { id: "agent-ada", name: "Ada" },
  { id: "agent-bos", name: "Bos Lang" },
  { id: "agent-cyd", name: "Cyd" },
];

describe("parseChannelMentions (row 31, feature-map)", () => {
  it("addresses a single @mention by name", () => {
    expect(parseChannelMentions("@ada please check", PARTICIPANTS))
      .toEqual({ addressed: ["agent-ada"], broadcast: false });
  });

  it("matches by id and is case-insensitive", () => {
    expect(parseChannelMentions("@Agent-Cyd @ADA go", PARTICIPANTS))
      .toEqual({ addressed: ["agent-ada", "agent-cyd"], broadcast: false });
  });

  it("matches a whitespace-stripped display name", () => {
    expect(parseChannelMentions("@boslang ping", PARTICIPANTS).addressed).toEqual(["agent-bos"]);
  });

  it("broadcasts when no participant is mentioned", () => {
    expect(parseChannelMentions("hey team, status?", PARTICIPANTS))
      .toEqual({ addressed: [], broadcast: true });
  });

  it("broadcasts when only unknown handles are mentioned", () => {
    expect(parseChannelMentions("@ghost hello", PARTICIPANTS).broadcast).toBe(true);
  });

  it("de-dupes repeated mentions, preserving participant order", () => {
    expect(parseChannelMentions("@cyd @ada @cyd", PARTICIPANTS).addressed)
      .toEqual(["agent-ada", "agent-cyd"]);
  });
});
