"use client";

import { useState } from "react";
import { MembersRoster } from "./members-roster";
import { CrewActivitySummary } from "./crew-activity-summary";
import type { RosterMember } from "./roster-filter";
import type { ActivityEvent } from "./activity-days";

/**
 * Row 30 (feature-map) — the Crew Members surface (`/members`).
 *
 * Composes the tested roster + activity surfaces: pick a member in the roster,
 * see their folded activity summary beside it. Data is INJECTED (`members` +
 * `activityFor`) so this is unit-testable with fixtures; the live crew→member
 * mapping + activity endpoint are the deferred backend (surfaced as an honest
 * empty state when no members are supplied). The docked SidePanel, DM threads,
 * and autonudge/slots wiring the full row calls for remain deferred too.
 */
export function MembersPage({ members, activityFor }: {
  members: readonly RosterMember[];
  activityFor?: (memberId: string) => readonly ActivityEvent[];
}) {
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const selected = members.find((m) => m.id === selectedId);

  return (
    <div className="flex h-full min-h-0 gap-4 p-4" aria-label="Crew Members">
      <div className="w-72 shrink-0">
        {members.length === 0 ? (
          <p className="rounded-md border border-border/40 bg-muted/20 p-3 text-[11px] text-muted-foreground">
            No crew members yet. The members data source (crew→member mapping, live state from
            slots/autonudge) is not wired on this deployment.
          </p>
        ) : (
          <MembersRoster members={members} selectedId={selectedId} onSelect={setSelectedId} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        {selected ? (
          <>
            <h2 className="mb-2 text-sm font-semibold">{selected.name}</h2>
            <CrewActivitySummary events={activityFor?.(selected.id) ?? []} />
          </>
        ) : (
          <p className="text-sm italic text-muted-foreground/70">Select a member to see their activity.</p>
        )}
      </div>
    </div>
  );
}
