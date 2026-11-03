import { NextResponse } from "next/server";

import type { LocalCredential, LocalCredentialSource } from "./mcp-local-credential";

/** Which credential source last got past the API; tried first so a stale one costs a single retry. */
let preferredSource: LocalCredentialSource | null = null;

/** Test hook: forget which credential source last worked. */
export function resetCredentialPreference(): void {
  preferredSource = null;
}

function ordered(candidates: LocalCredential[]): LocalCredential[] {
  if (preferredSource === null) return candidates;
  return [...candidates].sort((a, b) => Number(b.source === preferredSource) - Number(a.source === preferredSource));
}

const REJECTED_DESCRIPTION =
  "The local API rejected this dashboard's credential (a stale MCP_LOCAL_AUTH_TOKEN, or the API was restarted). "
  + "Restart the dashboard with scripts/companion-x-ui.sh.";

/** What the dashboard shows when every credential was refused: a cause and a fix, not the raw API body. */
export function rejectedResponse(): NextResponse {
  return NextResponse.json(
    { error: "invalid_token", error_description: REJECTED_DESCRIPTION },
    { status: 401, headers: { "cache-control": "private, no-store, max-age=0" } },
  );
}

/**
 * Send `init` with each credential in turn until the API stops answering 401.
 * The ambient token can outlive an API restart while the launcher file is
 * rewritten, so a 401 moves on to the next distinct token instead of failing.
 * Returns the last response (a 401 only when every credential was refused).
 */
export async function fetchWithCredentials(
  target: URL, init: RequestInit, credentials: LocalCredential[],
): Promise<Response | null> {
  let response: Response | null = null;
  for (const credential of ordered(credentials)) {
    const headers = new Headers(init.headers);
    headers.set("authorization", `Bearer ${credential.token}`);
    response = await fetch(target, { ...init, headers });
    if (response.status !== 401) { preferredSource = credential.source; return response; }
  }
  return response;
}
