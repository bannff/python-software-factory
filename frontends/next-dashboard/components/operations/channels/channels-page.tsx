"use client";

import { useState } from "react";
import { Hash } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChannelRoom } from "./channel-room";
import type { ChannelParticipant } from "./channel-mentions";

export interface Channel {
  id: string;
  name: string;
  participants: ChannelParticipant[];
}

/**
 * Row 31 (feature-map) — the Channels surface (`/channels`).
 *
 * Composes the channel list + `ChannelRoom` (addressing preview): pick a room,
 * compose to it. Data is INJECTED (`channels`) so it is unit-testable; the
 * rooms/membership backend + multi-agent turn fan-out are the deferred seam
 * (surfaced as an honest empty state when no channels are supplied).
 */
export function ChannelsPage({ channels }: { channels: readonly Channel[] }) {
  const [selectedId, setSelectedId] = useState<string | undefined>(channels[0]?.id);
  const selected = channels.find((c) => c.id === selectedId);

  return (
    <div className="flex h-full min-h-0 gap-4 p-4" aria-label="Channels">
      <div className="w-56 shrink-0">
        {channels.length === 0 ? (
          <p className="rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">
            No channels yet. The rooms/membership backend and multi-agent fan-out are not wired on
            this deployment.
          </p>
        ) : (
          <ul aria-label="Channel list" className="flex flex-col gap-1">
            {channels.map((c) => (
              <li key={c.id}>
                <button type="button" onClick={() => setSelectedId(c.id)}
                  aria-current={c.id === selectedId ? "true" : undefined}
                  className={cn("flex w-full items-center gap-1.5 rounded-md border px-2 py-1 text-left text-sm",
                    c.id === selectedId ? "border-violet-500/50 bg-violet-500/10" : "border-border/40 hover:bg-muted/40")}>
                  <Hash className="h-3.5 w-3.5 shrink-0 text-violet-400" />
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="min-w-0 flex-1">
        {selected
          ? <ChannelRoom name={selected.name} participants={selected.participants} />
          : <p className="text-sm italic text-muted-foreground/70">Select a channel.</p>}
      </div>
    </div>
  );
}
