"use client";

import { useMemo, useState } from "react";
import { Hash, Users } from "lucide-react";
import { parseChannelMentions, type ChannelParticipant } from "./channel-mentions";

/**
 * Row 31 (feature-map) — a Channel room surface (presentational).
 *
 * Composes the pure `parseChannelMentions` primitive (cycle 20) into the
 * group-room composer: shows the participant agents and a live "who receives
 * this" preview as the operator types — a specific @mention addresses that
 * agent, otherwise the message broadcasts to the whole room. Given
 * participants it renders; the multi-agent turn fan-out (each addressed agent
 * responds) + the rooms/membership backend are the deferred half.
 */
export function ChannelRoom({ name, participants }: {
  name?: string;
  participants: readonly ChannelParticipant[];
}) {
  const [draft, setDraft] = useState("");
  const addressing = useMemo(() => parseChannelMentions(draft, participants), [draft, participants]);
  const addressedNames = addressing.broadcast
    ? "Everyone"
    : participants.filter((p) => addressing.addressed.includes(p.id)).map((p) => p.name).join(", ");

  return (
    <div className="flex h-full flex-col gap-2" aria-label="Channel room">
      <span className="flex items-center gap-1.5 text-sm font-medium">
        <Hash className="h-4 w-4 text-violet-400" /> {name ?? "channel"}
      </span>
      <div className="flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
        <Users className="h-3.5 w-3.5" />
        {participants.map((p) => (
          <span key={p.id} className="rounded-full border border-border/40 px-1.5 py-0.5">{p.name}</span>
        ))}
      </div>
      <textarea value={draft} onChange={(e) => setDraft(e.target.value)}
        placeholder="Message the room… (@name to address one agent)" aria-label="Channel composer"
        className="min-h-16 rounded-md border border-border/60 bg-background/60 px-2.5 py-1 text-xs" />
      <p className="text-[11px] text-muted-foreground" aria-label="Addressing preview">
        Goes to: <span className="font-medium text-foreground">{addressedNames || "Everyone"}</span>
      </p>
      <p className="rounded-md border border-border/40 bg-muted/20 p-2 text-[11px] text-muted-foreground">
        Preview only: multi-agent turn fan-out (each addressed agent replies in-thread) and the
        rooms/membership backend are not wired on this deployment.
      </p>
    </div>
  );
}
