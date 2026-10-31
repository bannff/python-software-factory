"use client";

import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Users } from "lucide-react";
import { useCrews } from "@/lib/hooks/use-crews";
import { CrewCard } from "./crew-card";
import { CrewEditor } from "./crew-editor";
import type { Crew } from "./crew-types";

type Panel = { mode: "create" } | { mode: "edit"; crew: Crew } | null;

/**
 * Crews canvas — the owner-selected card gallery (M6.5 slice 4). Discoverable
 * crew cards in a 2–3 column grid with a Default badge and materialized
 * summaries, a dashed New-crew card, and a focused create/edit panel. Loading,
 * empty, and error/retry states are all truthful. Matches the Artifacts
 * library visual language.
 */
export default function CrewsView() {
  const { crews, defaultId, loading, error, refresh } = useCrews();
  const [panel, setPanel] = useState<Panel>(null);

  useEffect(() => {
    const parts = window.location.pathname.split("/").filter(Boolean);
    if (parts[0] === "crews" && parts[1]) {
      const id = decodeURIComponent(parts[1]);
      const match = crews.find((crew) => crew.id === id);
      if (match) setPanel({ mode: "edit", crew: match });
    }
  }, [crews]);

  return (
    <section className="mx-auto flex min-h-full w-full max-w-7xl flex-col gap-5 p-6" aria-labelledby="crews-title">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-400">Teams</p>
          <h1 id="crews-title" className="mt-1 text-2xl font-semibold tracking-tight">Crews</h1>
          <p className="mt-1 text-sm text-muted-foreground">Reusable crew configs — persona, project, model, and memory in one bundle.</p>
        </div>
        <button type="button" onClick={refresh} aria-label="Refresh crews"
          className="rounded-lg border border-border/60 p-2 text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </header>

      {error && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <span>Crews unavailable: {error}</span>
          <button type="button" onClick={refresh} className="rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-muted/50">Retry</button>
        </div>
      )}

      {loading && crews.length === 0 && !error && (
        <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading crews…
        </div>
      )}

      {panel && (
        <CrewEditor
          crew={panel.mode === "edit" ? panel.crew : null}
          isDefault={panel.mode === "edit" && panel.crew.id === defaultId}
          onSaved={refresh}
          onClose={() => setPanel(null)}
        />
      )}

      {!error && !(loading && crews.length === 0) && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {crews.map((crew) => (
            <CrewCard
              key={crew.id}
              crew={crew}
              isDefault={crew.id === defaultId}
              onOpen={() => setPanel({ mode: "edit", crew })}
            />
          ))}
          <button
            type="button"
            onClick={() => setPanel({ mode: "create" })}
            aria-label="New crew"
            className="flex min-h-[168px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border/60 p-4 text-center text-muted-foreground transition-colors hover:border-violet-500/50 hover:bg-violet-500/[0.03] hover:text-foreground"
          >
            <span className="rounded-lg bg-violet-500/10 p-2 text-violet-400"><Plus className="h-4 w-4" /></span>
            <span className="text-sm font-medium">New crew</span>
            {crews.length === 0 && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground/70">
                <Users className="h-3 w-3" /> No crews yet — create your first.
              </span>
            )}
          </button>
        </div>
      )}
    </section>
  );
}
