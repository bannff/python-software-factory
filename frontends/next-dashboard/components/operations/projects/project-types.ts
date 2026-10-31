import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Task Runner (Agent Capabilities → Projects) domain types + strict parsers.
 *
 * Backed by the Workflow brick's durable loop ledger (``workflow.start_loop`` /
 * ``list_loops`` / ``get_loop`` / ``get_loop_cycle`` / pause/resume/stop
 * transitions) — the same engine that drives Companion-X's own goal loop
 * (M7.6). No new backend: a spec's title/body map onto the loop's existing
 * ``objective``/``cycle_instructions`` fields. Identity/origin/project_root
 * are ambient on the backend; never sent from here.
 */

export type LoopKind = "goal" | "monitor";
export type LoopState = "active" | "paused" | "stopped" | "completed";

const KINDS = new Set<LoopKind>(["goal", "monitor"]);
const STATES = new Set<LoopState>(["active", "paused", "stopped", "completed"]);

export interface Loop {
  loopId: string;
  agentId: string;
  kind: LoopKind;
  objective: string;
  cycleInstructions: string;
  intervalSeconds: number;
  maxCycles: number;
  state: LoopState;
  terminalReason: string | null;
  nextCycle: number;
  lastSettledCycle: number;
  revision: number;
  createdAt: string;
}

export interface LoopCycle {
  cycle: number;
  state: "pending" | "scheduled" | "running" | "settled";
  disposition: string | null;
  summary: string | null;
}

export type LoopErrorKind = "conflict" | "deleted" | "error";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseLoop(raw: unknown): Loop | null {
  if (!isRecord(raw)) return null;
  const kind = raw.kind;
  const state = raw.state;
  if (typeof raw.loop_id !== "string" || !raw.loop_id) return null;
  if (typeof raw.agent_id !== "string") return null;
  if (typeof raw.objective !== "string" || typeof raw.cycle_instructions !== "string") return null;
  if (typeof kind !== "string" || !KINDS.has(kind as LoopKind)) return null;
  if (typeof state !== "string" || !STATES.has(state as LoopState)) return null;
  if (!Number.isInteger(raw.revision) || (raw.revision as number) < 1) return null;
  return {
    loopId: raw.loop_id, agentId: raw.agent_id, kind: kind as LoopKind,
    objective: raw.objective, cycleInstructions: raw.cycle_instructions,
    intervalSeconds: Number.isInteger(raw.interval_seconds) ? (raw.interval_seconds as number) : 300,
    maxCycles: Number.isInteger(raw.max_cycles) ? (raw.max_cycles as number) : 24,
    state: state as LoopState,
    terminalReason: typeof raw.terminal_reason === "string" ? raw.terminal_reason : null,
    nextCycle: Number.isInteger(raw.next_cycle) ? (raw.next_cycle as number) : 1,
    lastSettledCycle: Number.isInteger(raw.last_settled_cycle) ? (raw.last_settled_cycle as number) : 0,
    revision: raw.revision as number,
    createdAt: typeof raw.created_at === "string" ? raw.created_at : "",
  };
}

export function parseLoopList(raw: unknown): Loop[] {
  const data = unwrapToolData(raw);
  const rows = isRecord(data) && Array.isArray(data.loops) ? data.loops : [];
  return rows.map(parseLoop).filter((l): l is Loop => l !== null);
}

export function parseLoopOutput(raw: unknown): Loop {
  const data = unwrapToolData(raw);
  const loop = isRecord(data) ? parseLoop(data.loop) : null;
  if (!loop) throw new Error("loop_unparseable");
  return loop;
}

export function parseLoopCycle(raw: unknown): LoopCycle | null {
  const data = unwrapToolData(raw);
  const cycle = isRecord(data) ? data.cycle : null;
  if (!isRecord(cycle) || !Number.isInteger(cycle.cycle)) return null;
  const state = cycle.state;
  if (typeof state !== "string") return null;
  return {
    cycle: cycle.cycle as number, state: state as LoopCycle["state"],
    disposition: typeof cycle.disposition === "string" ? cycle.disposition : null,
    summary: typeof cycle.summary === "string" ? cycle.summary : null,
  };
}

export function classifyLoopError(error: unknown): LoopErrorKind {
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (message.includes("conflict")) return "conflict";
  if (message.includes("not_found")) return "deleted";
  return "error";
}
