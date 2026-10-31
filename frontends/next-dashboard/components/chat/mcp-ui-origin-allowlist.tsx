"use client";

/**
 * Origin allowlist UX for mcp-ui external_url resources
 * (bd:python-factory-eyahj — EPIC python-factory-lo1g9).
 *
 * Per security-engineer verdict
 * `d580bfdd-8928-47a4-8d73-a899328e128e` §6:
 *
 *   "first-time external_url from new origin → host modal asking
 *   allow-this-thread/always/never; per-server origin allowlist
 *   persisted in user settings (memory brick if Dolt available,
 *   localStorage v1; full origin match no wildcards)"
 *
 * v1 ships localStorage. The memory-brick variant is a follow-up bd
 * (cited in the verdict but out-of-scope for lo1g9.4).
 *
 * Storage shape under key `mcp-ui:origin-allowlist:v1`:
 *   { [origin: string]: "always" }
 *
 * "this-thread" decisions live in component state and don't
 * persist. "never" is implicit (we just don't render). No wildcards,
 * no `*.example.com` syntax — every entry is a full origin match.
 */

import { useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "mcp-ui:origin-allowlist:v1";

type AllowlistEntry = "always";
type Allowlist = Record<string, AllowlistEntry>;

function readAllowlist(): Allowlist {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed as Allowlist;
    return {};
  } catch {
    return {};
  }
}

function writeAllowlist(next: Allowlist): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* swallow quota / private-mode errors */
  }
}

export function isOriginAllowed(origin: string): boolean {
  const list = readAllowlist();
  return list[origin] === "always";
}

export function rememberOriginAlways(origin: string): void {
  const next = { ...readAllowlist(), [origin]: "always" as const };
  writeAllowlist(next);
}

/** Extract the iframe origin from a uri-list resource body. */
export function originFromUriList(body: string): string | null {
  if (typeof body !== "string") return null;
  const first = body
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l && !l.startsWith("#"));
  if (!first) return null;
  try {
    return new URL(first).origin;
  } catch {
    return null;
  }
}

interface OriginAllowlistGateProps {
  origin: string;
  serverLabel: string;
  children: React.ReactNode;
}

/**
 * Gates a child renderer behind a per-origin confirm prompt.
 *
 * Decision matrix:
 *   - persisted "always" → render immediately (skip modal).
 *   - in-memory "this-thread" → render until unmount.
 *   - undecided → render the confirm card; child stays hidden.
 */
export function OriginAllowlistGate({
  origin,
  serverLabel,
  children,
}: OriginAllowlistGateProps) {
  const persistedAllowed = useMemo(() => isOriginAllowed(origin), [origin]);
  const [decision, setDecision] = useState<
    "pending" | "this-thread" | "always" | "never"
  >(persistedAllowed ? "always" : "pending");

  // Re-evaluate when origin changes (different uri).
  useEffect(() => {
    setDecision(isOriginAllowed(origin) ? "always" : "pending");
  }, [origin]);

  if (decision === "this-thread" || decision === "always") {
    return <>{children}</>;
  }

  if (decision === "never") {
    return (
      <div
        data-testid="mcp-ui-origin-blocked"
        className="ml-11 my-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm"
        role="status"
      >
        Blocked external UI from <code>{origin}</code>.
      </div>
    );
  }

  return (
    <div
      data-testid="mcp-ui-origin-confirm"
      role="alertdialog"
      aria-labelledby="mcp-ui-origin-title"
      className="ml-11 my-2 rounded-xl border border-amber-300/40 bg-amber-50/40 dark:bg-amber-950/20 p-4 text-sm"
    >
      <p id="mcp-ui-origin-title" className="font-medium">
        Render external UI from <code>{origin}</code>?
      </p>
      <p className="text-xs text-muted-foreground mt-1">
        Server: <code>{serverLabel}</code>. The frame will run with
        <code> sandbox=&quot;allow-scripts&quot;</code> and a strict CSP.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-md bg-foreground/90 px-3 py-1 text-xs text-background hover:bg-foreground"
          onClick={() => setDecision("this-thread")}
        >
          Allow this thread
        </button>
        <button
          type="button"
          className="rounded-md border border-border px-3 py-1 text-xs hover:bg-muted/40"
          onClick={() => {
            rememberOriginAlways(origin);
            setDecision("always");
          }}
        >
          Always allow this origin
        </button>
        <button
          type="button"
          className="rounded-md border border-border px-3 py-1 text-xs hover:bg-muted/40"
          onClick={() => setDecision("never")}
        >
          Never
        </button>
      </div>
    </div>
  );
}
