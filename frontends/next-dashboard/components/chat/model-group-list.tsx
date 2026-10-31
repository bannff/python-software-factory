"use client";

import { useMemo } from "react";
import { Check } from "lucide-react";
import {
  applyRenderCap, cheapestModelId, formatPricing, type ProviderGroup,
} from "@/lib/model-catalog";
import { cn } from "@/lib/utils";

interface ModelGroupListProps {
  groups: ProviderGroup[];
  query: string;
  selectedModelId: string | null;
  disabled: boolean;
  onPick: (modelId: string) => void;
}

/** Filter groups by a case-insensitive substring over model and provider. */
export function filterGroups(groups: ProviderGroup[], query: string): ProviderGroup[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return groups;
  return groups
    .map((group) => ({
      ...group,
      models: group.models.filter((model) =>
        `${group.provider} ${model.model} ${model.model_id}`.toLowerCase().includes(needle)),
    }))
    .filter((group) => group.models.length > 0);
}

export function ModelGroupList({ groups, query, selectedModelId, disabled, onPick }: ModelGroupListProps) {
  const matched = useMemo(() => filterGroups(groups, query), [groups, query]);
  // The filter decides WHICH rows match; the cap only limits what is rendered,
  // so a revealed 450+ row provider catalog stays usable without virtualization.
  const { groups: visible, hidden } = useMemo(() => applyRenderCap(matched), [matched]);
  // Ranked over every MATCHED row: a row beyond the cap must never let a
  // pricier rendered row claim the "cheapest" badge.
  const cheapestId = useMemo(() => cheapestModelId(matched.flatMap((group) => group.models)), [matched]);
  if (matched.length === 0) {
    return <div className="px-2 py-1.5 text-muted-foreground/60">
      {query.trim() ? "No models match" : "No models configured"}</div>;
  }
  return (
    <div role="listbox" aria-label="Chat models" className="max-h-72 overflow-y-auto">
      {visible.map((group) => (
        <div key={group.provider} className="flex flex-col gap-0.5">
          <div className="px-2 pt-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/50">
            {group.provider} <span className="normal-case tracking-normal">· {group.models.length}</span>
          </div>
          {group.models.map((choice) => {
            const pricing = formatPricing(choice);
            return (
              <button
                key={choice.model_id}
                type="button"
                role="option"
                aria-selected={selectedModelId === choice.model_id}
                onClick={() => onPick(choice.model_id)}
                disabled={disabled}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-accent/50 disabled:opacity-60",
                  selectedModelId === choice.model_id && "bg-accent/40",
                )}
                title={pricing ? `${choice.model_id} — ${pricing}` : choice.model_id}
              >
                <Check className={cn("h-3 w-3 shrink-0", selectedModelId === choice.model_id ? "text-emerald-400" : "text-transparent")} />
                <span className="min-w-0 flex-1 truncate font-medium text-foreground">{choice.model}</span>
                {choice.configured === false && (
                  <span className="shrink-0 rounded-full bg-muted/40 px-1.5 py-0.5 text-[9px] font-medium text-muted-foreground/80">
                    not configured
                  </span>
                )}
                {choice.model_id === cheapestId && (
                  <span className="shrink-0 rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300">
                    cheapest
                  </span>
                )}
                {pricing && (
                  <span className="shrink-0 text-[10px] text-muted-foreground/60">{pricing}</span>
                )}
              </button>
            );
          })}
        </div>
      ))}
      {hidden > 0 && (
        <div className="px-2 py-1.5 text-[10px] text-muted-foreground/60">
          …and {hidden} more — keep typing to narrow
        </div>
      )}
    </div>
  );
}
