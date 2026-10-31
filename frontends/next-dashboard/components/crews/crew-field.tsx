"use client";

import { cloneElement, useState, type ReactElement, type ReactNode } from "react";
import { Info } from "lucide-react";
import { CREW_FIELD_HINTS, type CrewFieldKey } from "./crew-field-hints";

/** Shared input style for every Crews-form control. */
export const FIELD =
  "w-full rounded-md border border-border/60 bg-background/40 px-2.5 py-2 text-sm outline-none focus-visible:ring-1 focus-visible:ring-ring";
const LABEL = "text-[11px] font-medium text-muted-foreground";

/**
 * Keyboard-reachable ⓘ affordance. The trigger is a real `<button>`; the hint
 * element is always in the DOM and linked to the control via `aria-describedby`
 * (injected by `<Field>`), so it is announced without a pointer and toggled
 * visibly on focus/click. No hover-only `title` (issue #140).
 */
export function InfoHint({ id, label, hint }: { id: string; label: string; hint: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-full text-muted-foreground/70 outline-none hover:text-foreground focus-visible:ring-1 focus-visible:ring-ring"
      >
        <Info className="h-3 w-3" aria-hidden="true" />
      </button>
      <span
        id={id}
        role="note"
        hidden={!open}
        className="absolute left-0 top-5 z-10 w-64 rounded-md border border-border/60 bg-background p-2 text-[11px] leading-snug text-muted-foreground shadow-md"
      >
        {hint}
      </span>
    </span>
  );
}

/** Label + ⓘ hint + control, wired to `CREW_FIELD_HINTS` in one place. */
export function Field({ field, className, note, children }: {
  field: CrewFieldKey;
  className?: string;
  note?: ReactNode;
  children: ReactElement<{ id?: string; "aria-describedby"?: string }>;
}) {
  const { label, hint } = CREW_FIELD_HINTS[field];
  const hintId = `crew-${field}-hint`;
  // The ⓘ trigger MUST NOT live inside the <label>: `button` is itself a
  // labelable element, so a label wrapping it would take the trigger as its
  // labeled control and drop the field's own control out of the association.
  // The label is therefore tied to the control by explicit htmlFor/id.
  const controlId = `crew-${field}-control`;
  return (
    <div className={`flex flex-col gap-1 ${className ?? ""}`}>
      <span className={`${LABEL} flex items-center gap-1`}>
        <label htmlFor={controlId}>{label}</label>
        <InfoHint id={hintId} label={label} hint={hint} />
      </span>
      {cloneElement(children, { id: controlId, "aria-describedby": hintId })}
      {note}
    </div>
  );
}
