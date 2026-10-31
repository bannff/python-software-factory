"use client";

import { WifiOff, Box, Wrench, GitBranch, ExternalLink, Search } from "lucide-react";
import { motion } from "framer-motion";
import { useState } from "react";
import { NumberTicker } from "@/components/ui/number-ticker";
import { Popover } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/**
 * Repository identity is configuration, never a hardcoded provider (#156).
 * Set NEXT_PUBLIC_REPO_LABEL / NEXT_PUBLIC_REPO_URL / NEXT_PUBLIC_GIT_BRANCH in
 * the deployment's env; unset means "local workspace" with no outbound link.
 */
const REPO_LABEL = process.env.NEXT_PUBLIC_REPO_LABEL?.trim() || "local workspace";
const REPO_URL = process.env.NEXT_PUBLIC_REPO_URL?.trim() || "";
const GIT_BRANCH = process.env.NEXT_PUBLIC_GIT_BRANCH?.trim() || "";

/* ── Connection popover ─────────────────────────────────────────── */

export function ConnectionItem({
  connected,
  status,
  lastChecked,
}: {
  connected: boolean;
  status: string;
  lastChecked: number | null;
}) {
  const ago = lastChecked ? `${Math.round((Date.now() - lastChecked) / 1000)}s ago` : "—";
  const color = connected
    ? "text-emerald-600 dark:text-emerald-400"
    : "text-red-600 dark:text-red-400";

  return (
    <Popover
      trigger={
        <div className={cn("flex items-center gap-1.5", color)}>
          {connected ? <PulsingDot /> : <WifiOff className="h-3 w-3" />}
          <span>{connected ? "Connected" : "Disconnected"}</span>
        </div>
      }
    >
      <div className="space-y-2">
        <div className="font-medium text-foreground">MCP Gateway</div>
        <Row label="Status" value={status} className={color} />
        <Row label="Endpoint" value="/api/health" />
        <Row label="Last check" value={ago} />
        <Row label="Poll interval" value="30s" />
      </div>
    </Popover>
  );
}

/* ── Brick explorer popover ─────────────────────────────────────── */

export function BrickItem({
  brickCount,
  healthyBricks,
  bricks,
}: {
  brickCount: number;
  healthyBricks: number | null;
  bricks: Record<string, { healthy: boolean; error: string | null }>;
}) {
  const [filter, setFilter] = useState("");
  const entries = Object.entries(bricks).filter(([name]) =>
    name.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <Popover
      trigger={
        <div className="flex items-center gap-1 text-muted-foreground">
          <Box className="h-3 w-3" />
          <NumberTicker value={brickCount} />
          <span>bricks</span>
        </div>
      }
      className="w-[260px] max-h-[320px]"
    >
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-medium text-foreground">Brick Health</span>
          <span className="text-muted-foreground">
            {healthyBricks ?? 0}/{brickCount} healthy
          </span>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Filter bricks…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full rounded-md border border-border/50 bg-background/50 py-1 pl-7 pr-2 text-xs outline-none focus:border-primary/50"
          />
        </div>
        <div className="max-h-[200px] overflow-y-auto space-y-0.5">
          {entries.map(([name, info]) => (
            <div key={name} className="flex items-center gap-2 rounded px-1.5 py-1 hover:bg-accent/30">
              <span className={cn("h-1.5 w-1.5 rounded-full", info.healthy ? "bg-emerald-500" : "bg-red-500")} />
              <span className="text-foreground">{name}</span>
              {info.error && (
                <span className="ml-auto text-red-400 truncate max-w-[100px]" title={info.error}>
                  {info.error}
                </span>
              )}
            </div>
          ))}
          {entries.length === 0 && (
            <div className="text-muted-foreground py-2 text-center">No matches</div>
          )}
        </div>
      </div>
    </Popover>
  );
}

/* ── Tool catalog popover ───────────────────────────────────────── */

export function ToolItem({ totalTools }: { totalTools: number }) {
  return (
    <Popover
      trigger={
        <div className="flex items-center gap-1 text-muted-foreground">
          <Wrench className="h-3 w-3" />
          <NumberTicker value={totalTools} />
          <span>tools</span>
        </div>
      }
    >
      <div className="space-y-2">
        <div className="font-medium text-foreground">MCP Tools</div>
        <Row label="Total registered" value={String(totalTools)} />
        <p className="text-muted-foreground leading-relaxed">
          Use <span className="font-mono text-foreground">list_bricks</span> →{" "}
          <span className="font-mono text-foreground">get_brick_tools</span> to explore.
          Or ask in chat: &quot;List available tools&quot;
        </p>
      </div>
    </Popover>
  );
}

/* ── Git popover ────────────────────────────────────────────────── */

export function GitItem() {
  return (
    <Popover
      align="right"
      trigger={
        <div className="flex items-center gap-1 text-muted-foreground">
          <GitBranch className="h-3 w-3" />
          <span>{GIT_BRANCH || "git"}</span>
        </div>
      }
    >
      <div className="space-y-2">
        <div className="font-medium text-foreground">Repository</div>
        {GIT_BRANCH && <Row label="Branch" value={GIT_BRANCH} />}
        <Row label="Remote" value={REPO_LABEL} />
        {REPO_URL && (
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-primary hover:underline mt-1"
          >
            <ExternalLink className="h-3 w-3" />
            Open repository
          </a>
        )}
      </div>
    </Popover>
  );
}

/* ── Shared helpers ─────────────────────────────────────────────── */

export function PulsingDot() {
  return (
    <span className="relative flex h-2 w-2">
      <motion.span
        className="absolute inline-flex h-full w-full rounded-full bg-emerald-400"
        animate={{ scale: [1, 1.8, 1], opacity: [0.7, 0, 0.7] }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500 dark:bg-emerald-400" />
    </span>
  );
}

function Row({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-mono", className)}>{value}</span>
    </div>
  );
}
