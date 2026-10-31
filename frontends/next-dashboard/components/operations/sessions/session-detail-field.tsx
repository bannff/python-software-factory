"use client";

/** A labelled read-only field row for the session detail's metadata list. */
export function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      <dt className="shrink-0 text-muted-foreground/60">{label}</dt>
      <dd className="m-0 min-w-0 flex-1 truncate font-medium text-foreground/90" title={value}>{value}</dd>
    </div>
  );
}
