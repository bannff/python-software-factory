"use client";

import type { LucideIcon } from "lucide-react";
import { sendPrompt } from "@/lib/chat/send-prompt";

/**
 * The one empty-state shape: icon, a line, and optionally one action that sends
 * a prompt to the chat agent. Copy must never promise what no control offers.
 */
export function EmptyState({ icon: Icon, title, hint, action }: {
  icon: LucideIcon;
  title: string;
  hint?: string;
  action?: { icon: LucideIcon; label: string; prompt: string };
}) {
  const ActionIcon = action?.icon;
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
      <Icon className="h-6 w-6 text-muted-foreground/60" aria-hidden />
      <h2 className="text-sm font-medium">{title}</h2>
      {hint && <p className="max-w-sm text-xs text-muted-foreground">{hint}</p>}
      {action && ActionIcon && (
        <button type="button" onClick={() => sendPrompt(action.prompt)}
          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-1.5 text-xs hover:bg-accent/40">
          <ActionIcon className="h-3.5 w-3.5" aria-hidden /> {action.label}
        </button>
      )}
    </div>
  );
}
