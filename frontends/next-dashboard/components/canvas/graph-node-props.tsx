"use client";

import { useState } from "react";
import { CopyChip, ArnChip, fmtRelTime, renderHintFor } from "./graph-prop-chips";

function tryPrettyJson(val: string): string | null {
  try {
    const parsed = JSON.parse(val);
    if (typeof parsed === "object" && parsed !== null) return JSON.stringify(parsed, null, 2);
  } catch { /* not JSON */ }
  return null;
}

export function PropValue({ propKey, value }: { propKey?: string; value: unknown }) {
  const [expanded, setExpanded] = useState(false);
  const hint = propKey ? renderHintFor(propKey) : "default";

  if (hint === "copy_id" && typeof value === "string") return <CopyChip value={value} />;
  if (hint === "copy_arn" && typeof value === "string") return <ArnChip value={value} />;
  if (hint === "relative_time" && typeof value === "string") {
    return <span className="text-muted-foreground" title={value}>{fmtRelTime(value)}</span>;
  }

  const str = String(value);
  const pretty = typeof value === "string" ? tryPrettyJson(value) : null;
  const display = pretty ?? str;
  const long = display.length > 100;
  return (
    <span className="text-muted-foreground break-all">
      {long && !expanded ? display.slice(0, 100) + "…" : display}
      {long && <button onClick={() => setExpanded(!expanded)} className="ml-1 text-violet-400 hover:underline">{expanded ? "less" : "more"}</button>}
    </span>
  );
}

const IDENTITY_KEYS = new Set(["id", "name", "type", "labels", "version", "status"]);
const ACTIVITY_KEYS = new Set(["call_count", "last_called", "latency", "created_at", "updated_at", "timestamp", "count", "total"]);

export type PropGroup = "identity" | "activity" | "metadata";

export function groupFor(key: string): PropGroup {
  if (IDENTITY_KEYS.has(key)) return "identity";
  if (ACTIVITY_KEYS.has(key)) return "activity";
  return "metadata";
}

const GROUP_LABELS: Record<PropGroup, string> = { identity: "Identity", activity: "Activity", metadata: "Metadata" };

function PropSection({ group, entries }: { group: PropGroup; entries: Array<[string, unknown]> }) {
  if (entries.length === 0) return null;
  return (
    <div>
      <p className="text-[9px] font-semibold tracking-widest text-muted-foreground/50 uppercase mb-1">{GROUP_LABELS[group]}</p>
      <div className="space-y-1">
        {entries.map(([k, v]) => (
          <div key={k}><span className="font-medium text-foreground">{k}:</span>{" "}<PropValue propKey={k} value={v} /></div>
        ))}
      </div>
    </div>
  );
}

interface NodePropertiesProps {
  nodeId: string;
  groups: Record<PropGroup, Array<[string, unknown]>>;
  hasProps: boolean;
}

export function NodeProperties({ nodeId, groups, hasProps }: NodePropertiesProps) {
  return (
    <div className="space-y-2">
      <div>
        <p className="text-[9px] font-semibold tracking-widest text-muted-foreground/50 uppercase mb-1">Identity</p>
        <div className="space-y-1">
          <div><span className="font-medium text-foreground">id:</span>{" "}<CopyChip value={nodeId} /></div>
          {groups.identity.map(([k, v]) => (
            <div key={k}><span className="font-medium text-foreground">{k}:</span>{" "}<PropValue propKey={k} value={v} /></div>
          ))}
        </div>
      </div>
      <PropSection group="activity" entries={groups.activity} />
      <PropSection group="metadata" entries={groups.metadata} />
      {!hasProps && <p className="text-muted-foreground text-[11px] italic">No properties</p>}
    </div>
  );
}
