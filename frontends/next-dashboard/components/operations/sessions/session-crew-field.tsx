"use client";

import { Link2Off } from "lucide-react";
import type { Crew } from "@/components/crews/crew-types";
import { Field } from "./session-detail-field";

/**
 * The session's Crew, joined against the live roster. `crews` is undefined
 * while the roster is unknown (loading/failed): then the id is shown plain,
 * never mislabelled as removed.
 */
export function SessionCrewField({ crewId, crews }: { crewId: string; crews?: readonly Crew[] }) {
  if (!crewId) return <Field label="Crew" value="—" />;
  if (!crews) return <Field label="Crew" value={crewId} />;
  const crew = crews.find((candidate) => candidate.id === crewId);
  return (
    <div className="flex min-w-0 items-center gap-2">
      <dt className="shrink-0 text-muted-foreground/60">Crew</dt>
      {crew ? (
        <dd className="m-0 min-w-0 flex-1 truncate font-medium">
          <a href={`/crews/${encodeURIComponent(crew.id)}`} title={crew.id} className="text-violet-400 hover:underline">{crew.name}</a>
        </dd>
      ) : (
        <dd className="m-0 flex min-w-0 flex-1 items-center gap-1.5 truncate font-medium text-destructive/90" title={crewId}>
          <Link2Off className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>Crew removed</span>
          <span className="truncate text-muted-foreground/70">({crewId})</span>
        </dd>
      )}
    </div>
  );
}
