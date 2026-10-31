import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * Schedules surface domain types + strict parsers (M7 Operations, Option A).
 *
 * Shapes mirror the scheduler brick's ``ScheduleRecord`` / ``FireRecord``
 * (owner-scoped, revisioned) exactly as serialized by the real
 * ``scheduler_*`` MCP tools. Identity is ambient on the backend — no
 * tenant/owner is ever parsed or sent. Rows are parsed defensively: a
 * degraded or partial record is dropped rather than crashing the list.
 */

export type ScheduleKind = "interval" | "one_shot" | "cron";
export type ScheduleState = "active" | "paused" | "auto_paused" | "completed";
export type FireOutcome = "succeeded" | "failed" | "cancelled" | "running";

const KINDS = new Set<ScheduleKind>(["interval", "one_shot", "cron"]);
const STATES = new Set<ScheduleState>(["active", "paused", "auto_paused", "completed"]);

export interface Schedule {
  scheduleId: string;
  agentId: string;
  task: string;
  kind: ScheduleKind;
  intervalSeconds: number | null;
  oneShotAt: string | null;
  cronExpression: string | null;
  timezone: string;
  skipDates: string[];
  strictSchedule: boolean;
  state: ScheduleState;
  nextFireAt: string | null;
  lastFireAt: string | null;
  fireSequence: number;
  consecutiveFailures: number;
  revision: number;
}

export interface LastFire {
  fireSequence: number;
  outcome: FireOutcome;
}

/** Conflict/deleted are the two lifecycle errors the UI must react to truthfully. */
export type ScheduleErrorKind = "conflict" | "deleted" | "error";

/** Fields for ``scheduler_add`` (agent-turn schedules only; timing axis). */
export interface ScheduleCreateInput {
  agentId: string;
  task: string;
  kind: ScheduleKind;
  intervalSeconds?: number;
  oneShotAt?: string;
  cronExpression?: string;
  timezoneName?: string;
}

/** True when the create form has everything ``scheduler_add`` requires for its kind. */
export function isCreateInputComplete(input: ScheduleCreateInput): boolean {
  if (!input.agentId.trim() || !input.task.trim()) return false;
  if (input.kind === "interval") return Number.isFinite(input.intervalSeconds) && (input.intervalSeconds ?? 0) > 0;
  if (input.kind === "one_shot") return Boolean(input.oneShotAt);
  return Boolean(input.cronExpression?.trim());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function strOrNull(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

function intOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** Parse one raw record into a ``Schedule``; returns null when unusable. */
export function parseSchedule(raw: unknown): Schedule | null {
  if (!isRecord(raw)) return null;
  const kind = raw.kind;
  const state = raw.state;
  if (typeof raw.schedule_id !== "string" || !raw.schedule_id) return null;
  if (typeof raw.agent_id !== "string" || typeof raw.task !== "string") return null;
  if (typeof kind !== "string" || !KINDS.has(kind as ScheduleKind)) return null;
  if (typeof state !== "string" || !STATES.has(state as ScheduleState)) return null;
  if (!Number.isInteger(raw.revision) || (raw.revision as number) < 1) return null;
  return {
    scheduleId: raw.schedule_id,
    agentId: raw.agent_id,
    task: raw.task,
    kind: kind as ScheduleKind,
    intervalSeconds: intOrNull(raw.interval_seconds),
    oneShotAt: strOrNull(raw.one_shot_at),
    cronExpression: strOrNull(raw.cron_expression),
    timezone: str(raw.timezone, "UTC"),
    skipDates: Array.isArray(raw.skip_dates)
      ? raw.skip_dates.filter((d): d is string => typeof d === "string")
      : [],
    strictSchedule: raw.strict_schedule === true,
    state: state as ScheduleState,
    nextFireAt: strOrNull(raw.next_fire_at),
    lastFireAt: strOrNull(raw.last_fire_at),
    fireSequence: Number.isInteger(raw.fire_sequence) ? (raw.fire_sequence as number) : 0,
    consecutiveFailures: Number.isInteger(raw.consecutive_failures)
      ? (raw.consecutive_failures as number)
      : 0,
    revision: raw.revision as number,
  };
}

/** Unwrap + validate the ``scheduler_list`` ToolResult into a schedule array. */
export function parseScheduleList(raw: unknown): Schedule[] {
  const data = unwrapToolData(raw);
  const rows = isRecord(data) && Array.isArray(data.schedules) ? data.schedules : [];
  return rows.map(parseSchedule).filter((s): s is Schedule => s !== null);
}

/** Unwrap + validate a single-schedule ToolResult (``scheduler_get`` etc.). */
export function parseScheduleOutput(raw: unknown): Schedule {
  const data = unwrapToolData(raw);
  const schedule = isRecord(data) ? parseSchedule(data.schedule) : null;
  if (!schedule) throw new Error("schedule_unparseable");
  return schedule;
}

const FIRE_OUTCOME: Record<string, FireOutcome> = {
  succeeded: "succeeded",
  failed: "failed",
  cancelled: "cancelled",
  claimed: "running",
  enrolled: "running",
};

/** Unwrap + map a ``scheduler_get_fire`` ToolResult to a plain outcome. */
export function parseLastFire(raw: unknown): LastFire | null {
  const data = unwrapToolData(raw);
  const fire = isRecord(data) ? data.fire : null;
  if (!isRecord(fire) || typeof fire.state !== "string") return null;
  const outcome = FIRE_OUTCOME[fire.state];
  if (!outcome || !Number.isInteger(fire.fire_sequence)) return null;
  return { fireSequence: fire.fire_sequence as number, outcome };
}

/**
 * Classify a thrown tool error into the lifecycle reaction the UI needs.
 * The raw backend codes (``schedule_revision_conflict`` / ``schedule_not_found``)
 * never reach the user — only the classification drives behaviour.
 */
export function classifyScheduleError(error: unknown): ScheduleErrorKind {
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (message.includes("conflict")) return "conflict";
  if (message.includes("not_found")) return "deleted";
  return "error";
}
