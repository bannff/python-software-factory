import { callTool, listTools } from "@/lib/api";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface ApprovalPolicy {
  toolNames: string[];
  revision: number;
}

function parse(raw: unknown): ApprovalPolicy {
  if (!raw || typeof raw !== "object") throw new Error("Approval list unavailable.");
  const value = raw as Record<string, unknown>;
  if (!Array.isArray(value.tool_names) || typeof value.revision !== "number"
      || !value.tool_names.every((name) => typeof name === "string")) {
    throw new Error("Approval list unavailable.");
  }
  return { toolNames: value.tool_names, revision: value.revision } as ApprovalPolicy;
}

export async function getApprovalPolicy(): Promise<ApprovalPolicy> {
  return parse(unwrapToolData(await callTool("agent_get_approval_policy")));
}

export async function updateApprovalPolicy(value: ApprovalPolicy): Promise<ApprovalPolicy> {
  return parse(unwrapToolData(await callTool("agent_update_approval_policy", {
    tool_names: value.toolNames, expected_revision: value.revision,
  })));
}

export async function listApprovalToolNames(): Promise<string[]> {
  const names = (await listTools()).tools.filter((name) => !name.startsWith("fe_"));
  return [...new Set(names)].sort((a, b) => a.localeCompare(b));
}
