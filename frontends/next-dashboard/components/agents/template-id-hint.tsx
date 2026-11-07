/** Shows the backend-published ID rule under the ID field; flags a mismatch inline. */
export function TemplateIdHint({ pattern, invalid }: { pattern: string | null; invalid: boolean }) {
  if (!pattern) return null;
  return (
    <p className={`-mt-2 text-[11px] ${invalid ? "text-destructive" : "text-muted-foreground"}`}>
      {invalid && <span role="alert">ID does not match the allowed format.</span>} Allowed: <code>{pattern}</code>
    </p>
  );
}
