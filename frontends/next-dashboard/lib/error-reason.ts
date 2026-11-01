/** What the server said went wrong, or undefined when it said nothing specific.
 * `ApiError` carries it as `reason`; errors thrown by `unwrapToolData` carry it
 * as their message. Duck-typed so UI code need not import the API client. */
export function errorReason(error: unknown): string | undefined {
  if (!(error instanceof Error)) return undefined;
  if ("reason" in error) return typeof error.reason === "string" ? error.reason : undefined;
  return error.message || undefined;
}

/** Operator-facing text: the component's own prose plus the server's reason. */
export function withReason(prose: string, reason: string | undefined): string {
  return reason ? `${prose} (${reason})` : prose;
}
