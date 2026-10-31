import { unwrapToolData } from "@/lib/tool-result-data";

/**
 * A Crew is typed configuration data (M6.5), not a runtime.
 *
 * Shape mirrors the agent brick's ``CrewRecordDTO`` (owner-scoped, revisioned).
 * Parsed defensively from ``agent_list_crews`` so a degraded or partial row
 * never crashes the gallery — it is simply dropped.
 */
export interface Crew {
  id: string;
  name: string;
  description: string;
  persona_id: string;
  project: string;
  workspace: string;
  memory_scope: string;
  model: string;
  triggers: string[];
  revision: number;
}

export interface CrewRoster {
  crews: Crew[];
  defaultId: string | null;
}

export interface ResolvedCrew {
  crew_id: string;
  persona_id: string;
  model_id: string;
  project: string;
  workspace: string;
  memory_scope: string;
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

export function parseResolvedCrew(raw: unknown): ResolvedCrew {
  const value = unwrapToolData(raw) as Record<string, unknown>;
  const keys = ["crew_id", "persona_id", "model_id", "project", "workspace", "memory_scope"];
  if (!value || keys.some((key) => typeof value[key] !== "string")) {
    throw new Error("Crew binding unavailable");
  }
  return value as unknown as ResolvedCrew;
}

/** Unwrap + validate the ``agent_list_crews`` ToolResult into a roster. */
export function parseRoster(raw: unknown): CrewRoster {
  const data = unwrapToolData(raw);
  const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
  const rows = Array.isArray(obj.crews) ? obj.crews : [];
  const crews = rows
    .filter((row): row is Record<string, unknown> => Boolean(row && typeof row === "object"))
    .filter((row) =>
      typeof row.id === "string" &&
      typeof row.name === "string" &&
      typeof row.persona_id === "string" &&
      Number.isInteger(row.revision),
    )
    .map((row) => ({
      id: row.id as string,
      name: row.name as string,
      description: str(row.description),
      persona_id: row.persona_id as string,
      project: str(row.project),
      workspace: str(row.workspace),
      memory_scope: str(row.memory_scope),
      model: str(row.model),
      triggers: Array.isArray(row.triggers)
        ? row.triggers.filter((t): t is string => typeof t === "string")
        : [],
      revision: row.revision as number,
    }));
  const defaultId = typeof obj.default_id === "string" ? obj.default_id : null;
  return { crews, defaultId };
}
