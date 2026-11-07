import { unwrapToolData } from "@/lib/tool-result-data";

export interface WorkflowDefinitionSummary {
  id: string;
  name: string;
  version: number;
  tags: string[];
}

export interface WorkflowRun {
  runId: string;
  workflowId: string;
  status: string;
  startedAt: string;
  updatedAt: string;
  error?: string;
}

function definitionRow(raw: unknown): WorkflowDefinitionSummary | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.id !== "string" || typeof value.name !== "string") return null;
  return {
    id: value.id, name: value.name,
    version: typeof value.version === "number" ? value.version : 1,
    tags: Array.isArray(value.tags) ? value.tags.filter((t): t is string => typeof t === "string") : [],
  };
}

/** Parse ``workflow.get_workflow_registry`` output: ``{workflows: [...]}``. */
export function parseDefinitions(raw: unknown): WorkflowDefinitionSummary[] {
  const data = unwrapToolData(raw) as { workflows?: unknown };
  return Array.isArray(data?.workflows)
    ? data.workflows.map(definitionRow).filter((v): v is WorkflowDefinitionSummary => v !== null)
    : [];
}

function runRow(raw: unknown): WorkflowRun | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.run_id !== "string" || typeof value.workflow_id !== "string") return null;
  return {
    runId: value.run_id, workflowId: value.workflow_id,
    status: typeof value.status === "string" ? value.status : "unknown",
    startedAt: typeof value.started_at === "string" ? value.started_at : "",
    updatedAt: typeof value.updated_at === "string" ? value.updated_at : "",
    ...(typeof value.error === "string" ? { error: value.error } : {}),
  };
}

/** Parse ``workflow.list_runs`` output: ``{runs: [...]}``. */
export function parseRuns(raw: unknown): WorkflowRun[] {
  const data = unwrapToolData(raw) as { runs?: unknown };
  return Array.isArray(data?.runs)
    ? data.runs.map(runRow).filter((v): v is WorkflowRun => v !== null)
    : [];
}

/** Parse ``workflow.start_run`` output: ``{run_id, status}``. */
export function parseStartRun(raw: unknown): { runId: string } | null {
  const data = unwrapToolData(raw) as { run_id?: unknown };
  return typeof data?.run_id === "string" ? { runId: data.run_id } : null;
}

/** Parse ``workflow.authoring.upsert_workflow_definition``/delete output: ``{ok}``. */
export function parseOk(raw: unknown): boolean {
  const data = unwrapToolData(raw) as { ok?: unknown };
  return data?.ok === true;
}

/** ``workflow.get_run`` output (``RunOutput``): the list row plus where the run is and what it took/produced. */
export interface WorkflowRunDetail extends WorkflowRun {
  currentStepId?: string;
  waitingForEventType?: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export function parseRunDetail(raw: unknown): WorkflowRunDetail | null {
  const data = unwrapToolData(raw);
  const base = runRow(data);
  if (!base) return null;
  const value = data as Record<string, unknown>;
  return {
    ...base,
    input: isObject(value.input) ? value.input : {},
    ...(typeof value.current_step_id === "string" ? { currentStepId: value.current_step_id } : {}),
    ...(typeof value.waiting_for_event_type === "string" ? { waitingForEventType: value.waiting_for_event_type } : {}),
    ...(isObject(value.result) ? { result: value.result } : {}),
  };
}
