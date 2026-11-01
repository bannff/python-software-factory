"use client";

import { useState, type ReactNode } from "react";

interface ConfirmDeleteProps {
  /** Accessible name of the trigger, e.g. "Delete hook auto-x"; the confirm button is "Confirm <lower-cased label>". */
  label: string;
  onConfirm: () => void;
  disabled?: boolean;
  /** Trigger content (icon and/or text). */
  children: ReactNode;
  className?: string;
}

/**
 * One destructive-action pattern for the app: the first click only arms, a
 * second explicit click confirms. Shared by every delete that has no undo.
 */
export function ConfirmDelete({ label, onConfirm, disabled, children, className }: ConfirmDeleteProps) {
  const [armed, setArmed] = useState(false);
  if (!armed) {
    return (
      <button type="button" aria-label={label} disabled={disabled} onClick={() => setArmed(true)} className={className}>
        {children}
      </button>
    );
  }
  const confirmLabel = `Confirm ${label.charAt(0).toLowerCase()}${label.slice(1)}`;
  return (
    <span role="group" aria-label="Confirm deletion" className="inline-flex items-center gap-1">
      <button type="button" aria-label={confirmLabel} disabled={disabled}
        onClick={() => { setArmed(false); onConfirm(); }}
        className="rounded-md bg-destructive px-2 py-1 text-[11px] font-medium text-destructive-foreground disabled:opacity-40">
        Delete permanently
      </button>
      <button type="button" onClick={() => setArmed(false)}
        className="rounded-md border border-border/60 px-2 py-1 text-[11px]">Cancel</button>
    </span>
  );
}
