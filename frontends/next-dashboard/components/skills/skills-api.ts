import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface SkillSummary {
  id: string;
  name: string;
  description: string;
}

export interface SkillDetail extends SkillSummary {
  body: string;
}

function summary(raw: unknown): SkillSummary | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  if (typeof value.id !== "string" || typeof value.name !== "string") return null;
  return { id: value.id, name: value.name,
    description: typeof value.description === "string" ? value.description : "" };
}

export async function listSkills(): Promise<SkillSummary[]> {
  const data = unwrapToolData(await callTool("agent_list_skills")) as { skills?: unknown };
  return Array.isArray(data?.skills)
    ? data.skills.map(summary).filter((row): row is SkillSummary => row !== null) : [];
}

export async function readSkill(skillId: string): Promise<SkillDetail> {
  const data = unwrapToolData(await callTool("agent_read_skill", { skill_id: skillId }));
  const row = summary(data);
  if (!row || !data || typeof data !== "object" || typeof (data as Record<string, unknown>).body !== "string") {
    throw new Error("Skill detail unavailable.");
  }
  return { ...row, body: (data as Record<string, unknown>).body as string };
}

export async function deleteSkill(skillId: string): Promise<void> {
  const data = unwrapToolData(await callTool("agent_delete_skill", {
    skill_id: skillId,
  })) as { deleted?: boolean };
  if (data?.deleted !== true) throw new Error("Skill could not be removed.");
}

export async function addSkill(input: {
  skillId: string; name: string; description: string; body: string;
}): Promise<SkillSummary> {
  const data = unwrapToolData(await callTool("agent_add_skill", {
    skill_id: input.skillId, name: input.name,
    description: input.description, body: input.body,
  })) as { created?: boolean; skill?: unknown };
  const row = summary(data?.skill);
  if (data?.created !== true || !row) throw new Error("Skill was not created.");
  return row;
}

/** Owner-scoped skill enablement policy (skills switched OFF for this owner). */
export interface SkillPolicy {
  disabledSkills: string[];
  revision: number;
}

function policyFrom(raw: unknown): SkillPolicy {
  const data = unwrapToolData(raw) as { disabled_skills?: unknown; revision?: unknown };
  if (!Array.isArray(data.disabled_skills) || typeof data.revision !== "number") throw new Error("Skill policy unavailable.");
  return { disabledSkills: data.disabled_skills.filter((s): s is string => typeof s === "string"), revision: data.revision };
}

export async function getSkillPolicy(): Promise<SkillPolicy> {
  return policyFrom(await callTool("agent_get_skill_policy"));
}

export async function updateSkillPolicy(disabledSkills: string[], expectedRevision: number): Promise<SkillPolicy> {
  return policyFrom(await callTool("agent_update_skill_policy", {
    disabled_skills: disabledSkills, expected_revision: expectedRevision,
  }));
}
