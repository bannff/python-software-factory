"use client";

/**
 * ⌘K command palette (bd:3jcls.4) — the human's way in.
 *
 * The problem it closes: every brick has an MCP interface so an AGENT can
 * drive it, and the UI was built to DISPLAY what the agent did. The ML
 * Overview literally reads "Ask the assistant to run the relevant MCP
 * operation" — the UI instructing the human to leave the UI. ~689 tools across
 * ~40 bricks already carry a name, a human description and a JSON input
 * schema, which is a complete command registry nobody has to hand-maintain.
 *
 * Zero persistent chrome: this renders `null` until summoned, which is exactly
 * why the palette was chosen over a dashboard of buttons.
 *
 * Scoped to `@operational` + `@authoring`. `@deterministic` reads are not
 * verbs a human fires, so they would only dilute the list.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useDisplayPreferences } from "@/components/settings/use-display-preferences";
import { effectiveChord, matchesChord } from "@/lib/shortcuts";
import {
  Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput,
  CommandItem, CommandList,
} from "@/components/ui/command";
import { useToolCatalog } from "@/lib/hooks/use-tool-catalog";
import { activeBrickFor, rankTools, type CatalogTool } from "@/lib/tool-catalog";
import { ToolLauncher } from "./tool-launcher";

const MAX_RESULTS = 60;

export function CommandPalette({ activeView }: { activeView?: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<CatalogTool | null>(null);
  const { catalog, loading, error } = useToolCatalog(open);

  const { preferences } = useDisplayPreferences();
  const chord = effectiveChord("command_palette", preferences.shortcuts);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!chord || event.repeat || !matchesChord(event, chord)) return;
      event.preventDefault();
      setOpen((prev) => !prev);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [chord]);

  const onOpenChange = useCallback((next: boolean) => {
    setOpen(next);
    if (!next) {
      setQuery("");
      setSelected(null);
    }
  }, []);

  const activeBrick = useMemo(
    () => (catalog ? activeBrickFor(activeView, catalog) : null),
    [activeView, catalog],
  );

  const ranked = useMemo(
    () => (catalog ? rankTools(catalog.tools, query, activeBrick) : []),
    [catalog, query, activeBrick],
  );
  const results = useMemo(() => ranked.slice(0, MAX_RESULTS), [ranked]);

  // Say "60 of 357" rather than "60 operations" — a truncated list that reads
  // like a complete one is the same lie the ML Overview told.
  const countLabel =
    ranked.length > results.length
      ? `${results.length} of ${ranked.length} operations`
      : `${results.length} operations`;

  if (!open) return null;

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} label="Command palette">
      {selected ? (
        <ToolLauncher tool={selected} onBack={() => setSelected(null)} />
      ) : (
        // `shouldFilter={false}` — ranking is ours (active brick first), and
        // cmdk keeps the listbox/option aria wiring and arrow-key navigation.
        <Command shouldFilter={false} loop label="Command palette">
          <CommandInput
            autoFocus
            value={query}
            onValueChange={setQuery}
            placeholder={
              loading ? "Loading tool catalog…" : "Run a brick operation…"
            }
          />
          <CommandList>
            {error ? (
              <div role="alert" className="p-3 text-[11px] text-destructive">
                {error}
              </div>
            ) : loading ? (
              <div className="p-3 text-[11px] text-muted-foreground">
                Loading every brick’s tools…
              </div>
            ) : (
              <>
                <CommandEmpty>No matching operation.</CommandEmpty>
                {results.length > 0 && (
                  <CommandGroup
                    heading={
                      activeBrick ? `${countLabel} · ${activeBrick} first` : countLabel
                    }
                  >
                    {results.map((tool) => (
                      <CommandItem
                        key={tool.qualified_name}
                        value={tool.qualified_name}
                        onSelect={() => setSelected(tool)}
                      >
                        <span className="w-28 shrink-0 truncate text-[10px] uppercase tracking-wider text-muted-foreground">
                          {tool.brick}
                        </span>
                        <span className="shrink-0 font-mono text-[11px]">{tool.name}</span>
                        <span className="truncate text-[11px] text-muted-foreground">
                          {tool.description}
                        </span>
                        {tool.category === "authoring" && (
                          <span className="ml-auto shrink-0 text-[10px] uppercase tracking-wider text-amber-500/80">
                            authoring
                          </span>
                        )}
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {catalog?.bricks_failed.length ? (
                  <div className="border-t border-border/60 px-3 py-1.5 text-[10px] text-amber-500/80">
                    {catalog.bricks_failed.length} brick(s) failed to load:{" "}
                    {catalog.bricks_failed.map((f) => f.brick).join(", ")}
                  </div>
                ) : null}
              </>
            )}
          </CommandList>
        </Command>
      )}
    </CommandDialog>
  );
}
