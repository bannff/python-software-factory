/**
 * Row 31 (feature-map) — Channels: group rooms with several agents in one
 * thread. This is the addressing primitive that a multi-agent room needs:
 * given a posted message, decide which participant agents it is directed at.
 *
 * A message may @mention specific participants (by id or display handle); if
 * it names none that resolve, it is a broadcast to the whole room. Pure and
 * self-contained so it is fully unit-testable ahead of the Channels surface +
 * backend (rooms, membership, multi-agent turn fan-out), which are deferred.
 */

export interface ChannelParticipant {
  id: string;
  name: string;
}

export interface ChannelAddressing {
  /** Participant ids explicitly addressed (in participant order, de-duped). */
  addressed: string[];
  /** True when no participant was explicitly addressed → the whole room. */
  broadcast: boolean;
}

function handle(value: string): string {
  return value.toLowerCase().replace(/\s+/g, "");
}

/**
 * Resolve @mentions in `text` against `participants`. A token matches a
 * participant by id or by whitespace-stripped, case-insensitive name. When no
 * token resolves to a participant, the message is a broadcast.
 */
export function parseChannelMentions(
  text: string,
  participants: readonly ChannelParticipant[],
): ChannelAddressing {
  const tokens = new Set(
    [...text.matchAll(/@([a-z0-9_-]+)/gi)].map((m) => m[1].toLowerCase()),
  );
  const addressed = participants
    .filter((p) => tokens.has(p.id.toLowerCase()) || tokens.has(handle(p.name)))
    .map((p) => p.id);
  // De-dupe while preserving participant order.
  const unique = [...new Set(addressed)];
  return { addressed: unique, broadcast: unique.length === 0 };
}
