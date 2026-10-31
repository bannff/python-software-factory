"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

export function CopyChip({ value, short }: { value: string; short?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard.writeText(value).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }); };
  return (
    <span className="inline-flex items-center gap-1 group cursor-default">
      <span className="font-mono text-muted-foreground break-all">{short ?? value.slice(0, 20)}</span>
      <button onClick={copy} className="opacity-0 group-hover:opacity-100 transition-opacity">
        {copied ? <Check className="h-2.5 w-2.5 text-emerald-400" /> : <Copy className="h-2.5 w-2.5 text-muted-foreground/60" />}
      </button>
    </span>
  );
}

export function ArnChip({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard.writeText(value).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }); };
  const short = value.split(":").slice(-2).join("/").slice(0, 35);
  return (
    <span className="inline-flex items-center gap-1 group cursor-default">
      <span className="font-mono text-muted-foreground text-[10px]">{short}</span>
      <button onClick={copy} className="opacity-0 group-hover:opacity-100 transition-opacity">
        {copied ? <Check className="h-2.5 w-2.5 text-emerald-400" /> : <Copy className="h-2.5 w-2.5 text-muted-foreground/60" />}
      </button>
    </span>
  );
}

export function fmtRelTime(val: string): string {
  try {
    const ms = Date.parse(val);
    if (isNaN(ms)) return val;
    const diff = Date.now() - ms;
    if (diff < 60_000) return `${Math.round(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
    return new Date(ms).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch { return val; }
}

export function renderHintFor(key: string): "copy_id" | "relative_time" | "copy_arn" | "default" {
  if (key.endsWith("_id") || key === "id") return "copy_id";
  if (key.endsWith("_at") || key === "timestamp" || key === "created_at" || key === "updated_at") return "relative_time";
  if (key.endsWith("_arn") || key === "arn" || key.includes("resource_arn")) return "copy_arn";
  return "default";
}
