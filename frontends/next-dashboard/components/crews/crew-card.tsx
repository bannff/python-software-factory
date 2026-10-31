"use client";

import { Cpu, Database, FolderGit2, Sparkles, Users } from "lucide-react";
import type { Crew } from "./crew-types";

function SummaryRow({ icon: Icon, label, value, hint }: {
  icon: typeof Cpu; label: string; value: string; hint: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2 text-xs">
      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
      <dt className="shrink-0 text-muted-foreground/60" title={hint}>
        {label}<span className="sr-only"> — {hint}.</span>
      </dt>
      <dd className="m-0 min-w-0 flex-1 truncate font-medium text-foreground/90" title={value}>{value}</dd>
    </div>
  );
}

/**
 * One discoverable Crew card. Shows a clear Default badge and the four
 * materialized summaries (persona, project, model, memory scope) so a
 * first-time user understands what the Crew binds without opening it.
 */
export function CrewCard({ crew, isDefault, onOpen }: {
  crew: Crew; isDefault: boolean; onOpen: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Edit crew ${crew.name}`}
      className="group flex min-w-0 flex-col gap-3 rounded-xl border border-border/60 bg-card/30 p-4 text-left transition-all hover:-translate-y-0.5 hover:border-violet-500/40 hover:bg-card/60 hover:shadow-lg hover:shadow-violet-500/5"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-3">
          <span className="rounded-lg bg-violet-500/10 p-2 text-violet-400"><Users className="h-4 w-4" /></span>
          <div className="min-w-0">
            <h3 className="truncate font-medium" title={crew.name}>{crew.name}</h3>
            <p className="truncate text-xs text-muted-foreground">{crew.id}</p>
          </div>
        </div>
        {isDefault && (
          <span className="shrink-0 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
            Default
          </span>
        )}
      </div>
      <p className="line-clamp-2 min-h-8 text-sm text-muted-foreground">
        {crew.description || "No description yet."}
      </p>
      <dl className="grid min-w-0 gap-1.5 border-t border-border/40 pt-3">
        <SummaryRow icon={Sparkles} label="Persona" value={crew.persona_id}
          hint="Which assistant personality this crew uses" />
        <SummaryRow icon={FolderGit2} label="Project" value={crew.project}
          hint="Which project folder this crew works in" />
        <SummaryRow icon={Cpu} label="Model" value={crew.model || "Inherit"}
          hint="Which AI engine this crew uses" />
        <SummaryRow icon={Database} label="Memory" value={crew.memory_scope || "—"}
          hint="Which saved context this crew can recall" />
      </dl>
    </button>
  );
}
