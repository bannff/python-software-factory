import { callTool } from "@/lib/api";
import { parseResolvedCrew, type ResolvedCrew } from "@/components/crews/crew-types";
import { parseSession, type SessionSummary } from "@/lib/hooks/use-session-list";
import { unwrapToolData } from "@/lib/tool-result-data";
import { requestQuestion } from "@/lib/mcp-question";

type Caller = typeof callTool;

export interface StartedCrewSession {
  crew: ResolvedCrew;
  session: SessionSummary;
}

function parseAllowedRoots(raw: unknown): string[] {
  const data = unwrapToolData(raw) as { roots?: unknown };
  if (!data || !Array.isArray(data.roots)) return [];
  return data.roots.filter((root): root is string => typeof root === "string" && root.length > 0);
}

/**
 * Ask the user which allowed project root to use instead, when the crew's
 * stored project falls outside `COMPANION_X_PROJECT_ALLOWED_ROOTS` (the
 * live "New session could not be created" dead end found and diagnosed
 * cycle 65; this closes it with a real choice instead of a bare failure).
 * Returns `null` if the user cancels or no alternative roots are configured.
 */
async function pickReplacementProject(caller: Caller): Promise<string | null> {
  const roots = parseAllowedRoots(await caller("devtools_list_allowed_project_roots", {}));
  if (roots.length === 0) return null;
  const decision = await requestQuestion(
    "This crew's saved project is outside the allowed roots. Pick one to use instead:",
    "project", roots,
  );
  return decision.action === "answer" ? decision.value : null;
}

/** Resolve the default Crew, then materialize it through Session's sole create path. */
export async function startDefaultCrewSession(
  crewId: string, caller: Caller = callTool,
): Promise<StartedCrewSession> {
  let crew: ResolvedCrew;
  try {
    crew = parseResolvedCrew(await caller("agent_resolve_crew", {
      crew_id: crewId,
    }));
  } catch {
    throw new Error("Default crew unavailable");
  }
  const create = (project: string) => caller("session_create", {
    title: "New session", agent_id: crew.persona_id, model: crew.model_id,
    workspace: crew.workspace, project, crew_id: crew.crew_id,
    memory_scope: crew.memory_scope, origin: "user",
  });
  try {
    const session = parseSession(await create(crew.project));
    return { crew, session };
  } catch (error) {
    if (!(error instanceof Error) || error.message !== "session_project_path_refused") {
      throw new Error("Default crew session could not be created");
    }
    const replacement = await pickReplacementProject(caller);
    if (!replacement) throw new Error("Default crew session could not be created");
    try {
      const session = parseSession(await create(replacement));
      return { crew, session };
    } catch {
      throw new Error("Default crew session could not be created");
    }
  }
}
