/**
 * Workbench types for the Companion X Security Workbench IDE layout.
 */

export type CanvasViewId =
  | "welcome"
  | "graph"
  | "timeline-v2"
  | "findings"
  | "evals"
  | "metrics"
  | "ml"
  | "games"
  | "blockchain"
  | "sandbox"
  | "capabilities"
  | "sessions"
  | "schedules"
  | "lessons"
  | "artifacts"
  | "crews"
  | "live"
  | "settings";

export type NavigationSurface = "graph" | "timeline" | "evals" | "owner" | "metrics";

export interface BoundedGraphContext {
  query_ref: string;
  neighborhood_limit: number;
}

export interface NavigationFocusOrigin {
  token: string;
  surface: "graph";
  control: "open-metrics";
}

export interface NavigationRef {
  version: "v1";
  surface: NavigationSurface;
  target_ref: string;
  label: string;
  graph_selected_ref: string | null;
  graph_context: BoundedGraphContext | null;
  focus_origin?: NavigationFocusOrigin | null;
}

export interface CanvasTab {
  id: string;
  viewId: CanvasViewId;
  label: string;
  closable: boolean;
}

export type FindingSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  id: string;
  severity: FindingSeverity;
  title: string;
  resource: string;
  type: string;
  description: string;
  evidence?: string;
  remediation?: string;
  timestamp: number;
  // Extended fields
  cwe?: string;
  category?: string;
  affected_resource_arn?: string;
  analysis_id?: string;
  analysis_target?: string;
  source?: "graph" | "live";
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  color: string;
  val: number;
  properties?: Record<string, unknown>;
}

export interface GraphLink {
  source: string;
  target: string;
  label?: string;
}

export interface TimelineEntry {
  id: string;
  type: "step" | "tool_call" | "finding" | "swarm_event";
  title: string;
  status: "running" | "completed" | "failed";
  timestamp: number;
  duration?: number;
  detail?: string;
  severity?: FindingSeverity;
  error?: string;
  /** Workflow run this invocation belongs to (propagated via envelope context) */
  workflow_run_id?: string;
  /** Session this invocation belongs to (propagated via envelope context) */
  session_id?: string;
  /** Agent responsible for the invocation's session when known from graph-backed history */
  agent_id?: string;
  /** Principal/user who initiated the invocation's session when known from graph-backed history */
  principal_id?: string;
  /** Swarm event subtype: node_start, handoff, node_stop, launched, completed, failed */
  swarmEventType?: string;
  /** Swarm-specific metadata */
  swarmMeta?: Record<string, unknown>;
  /** Bounded, redacted summary of tool arguments */
  args_summary?: Record<string, unknown>;
  /** Who invoked the tool (from envelope context) */
  caller?: string;
  /** Bounded extraction of key output fields */
  result_summary?: Record<string, unknown>;
}
