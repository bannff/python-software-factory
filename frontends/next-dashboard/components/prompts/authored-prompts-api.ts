import { callTool } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface PromptArg { name: string; description: string; required: boolean }
export interface AuthoredPrompt {
  prompt_id: string; description: string; template: string; arguments: PromptArg[]; revision: number;
}
export interface PromptInput {
  prompt_id: string; description: string; template: string; arguments: PromptArg[];
}

function rowFrom(raw: unknown): AuthoredPrompt | null {
  if (!raw || typeof raw !== "object") return null;
  const v = raw as Record<string, unknown>;
  if (typeof v.prompt_id !== "string" || typeof v.template !== "string" || typeof v.revision !== "number") return null;
  const args = Array.isArray(v.arguments) ? v.arguments.flatMap((a): PromptArg[] => {
    const x = a as Record<string, unknown>;
    return typeof x?.name === "string"
      ? [{ name: x.name, description: typeof x.description === "string" ? x.description : "", required: x.required === true }]
      : [];
  }) : [];
  return { prompt_id: v.prompt_id, description: typeof v.description === "string" ? v.description : "",
    template: v.template, arguments: args, revision: v.revision };
}

export async function listAuthoredPrompts(): Promise<AuthoredPrompt[]> {
  const data = unwrapToolData(await callTool("agent_list_prompts")) as { prompts?: unknown };
  return Array.isArray(data?.prompts)
    ? data.prompts.map(rowFrom).filter((r): r is AuthoredPrompt => r !== null) : [];
}

export async function addPrompt(input: PromptInput): Promise<AuthoredPrompt> {
  const data = unwrapToolData(await callTool("agent_add_prompt", {
    prompt_id: input.prompt_id, description: input.description,
    template: input.template, arguments: input.arguments,
  })) as { prompt?: unknown };
  const row = rowFrom(data?.prompt);
  if (!row) throw new Error("Prompt was not created.");
  return row;
}

export async function updatePrompt(input: PromptInput, expectedRevision: number): Promise<AuthoredPrompt> {
  const data = unwrapToolData(await callTool("agent_update_prompt", {
    prompt_id: input.prompt_id, expected_revision: expectedRevision, description: input.description,
    template: input.template, arguments: input.arguments,
  })) as { prompt?: unknown };
  const row = rowFrom(data?.prompt);
  if (!row) throw new Error("Prompt was not updated.");
  return row;
}

export async function deletePrompt(promptId: string): Promise<void> {
  const data = unwrapToolData(await callTool("agent_delete_prompt", { prompt_id: promptId })) as { deleted?: boolean };
  if (data?.deleted !== true) throw new Error("Prompt could not be removed.");
}
