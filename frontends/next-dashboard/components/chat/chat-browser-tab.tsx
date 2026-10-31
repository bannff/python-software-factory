"use client";

import { useState } from "react";
import { Globe } from "lucide-react";

/**
 * Row 26 (feature-map) — the Browser tab in the chat side panel.
 *
 * This slice ships the user-driven half the row names: "the non-native
 * address bar opens a real website in it" — a URL bar that loads the site in
 * an in-panel iframe. Deferred (needs backend/desktop): the AGENT driving the
 * browser (`/api/browser/*` view/command contract) and the desktop **Annotate**
 * flow (`browser:annotate` IPC) that picks page elements into chat — neither
 * exists in Companion-X. Also honest: many sites refuse to be embedded
 * (`X-Frame-Options`/CSP), which the panel discloses.
 */

/** Normalise a typed address into a loadable URL (bare host → https://). */
export function normalizeUrl(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const withScheme = /^[a-z]+:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    return new URL(withScheme).toString();
  } catch {
    return null;
  }
}

export function ChatBrowserTab() {
  const [draft, setDraft] = useState("");
  const [src, setSrc] = useState<string | null>(null);

  const go = () => {
    const url = normalizeUrl(draft);
    if (url) setSrc(url);
  };

  return (
    <div className="flex h-full flex-col gap-2" aria-label="Browser panel">
      <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-[0.15em] text-muted-foreground">
        <Globe className="h-3.5 w-3.5" /> Browser
      </span>
      <div className="flex gap-1.5">
        <input value={draft} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); go(); } }}
          placeholder="Enter a URL…" aria-label="Address bar"
          className="min-w-0 flex-1 rounded-md border border-border/60 bg-background/60 px-2.5 py-1 text-xs" />
        <button type="button" onClick={go}
          className="shrink-0 rounded-md border border-border/60 px-2.5 py-1 text-xs hover:bg-muted/50">Go</button>
      </div>
      {src ? (
        <iframe title="In-panel browser" src={src}
          sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
          className="min-h-0 flex-1 rounded-md border border-border/40 bg-white" />
      ) : (
        <p className="text-sm italic text-muted-foreground/70">Enter a URL to open a site in the panel.</p>
      )}
      <p className="rounded-md border border-border/40 bg-muted/20 p-2 text-[11px] text-muted-foreground">
        View-only: the agent cannot drive this browser and page **Annotate** is not wired on this
        deployment (both need the `/api/browser/*` backend / desktop IPC). Some sites refuse to embed.
      </p>
    </div>
  );
}
