import { callTool } from "@/lib/api";
import { errorReason, withReason } from "@/lib/error-reason";
import { unwrapToolData } from "@/lib/tool-result-data";

export interface Environment {
  env_id: string; status: string; instance_type: string; public_ip: string | null; profile: string | null; created_at: string;
}

const str = (v: unknown) => (typeof v === "string" ? v : "");

function environmentFrom(e: unknown): Environment | null {
  const v = e as Record<string, unknown> | null;
  if (typeof v?.env_id !== "string") return null;
  const profile = (v.metadata as { profile?: unknown } | undefined)?.profile;
  return { env_id: v.env_id, status: str(v.status), instance_type: str(v.instance_type), created_at: str(v.created_at),
    public_ip: typeof v.public_ip === "string" ? v.public_ip : null, profile: typeof profile === "string" ? profile : null };
}

/** The list can keep saying "provisioning" until someone asks for the environment itself, so ask. */
async function currentStatus(env: Environment): Promise<Environment> {
  if (env.status !== "provisioning") return env;
  try {
    const data = unwrapToolData(await callTool("sandbox_get_status", { env_id: env.env_id })) as { environment?: unknown } | null;
    return environmentFrom(data?.environment) ?? env;
  } catch { return env; }
}

export async function listEnvironments(): Promise<Environment[]> {
  const data = unwrapToolData(await callTool("sandbox_list_environments")) as { environments?: unknown };
  const listed = Array.isArray(data?.environments) ? data.environments.map(environmentFrom).filter((e): e is Environment => e !== null) : [];
  return Promise.all(listed.map(currentStatus));
}

const names = (raw: unknown, key: string): string[] => {
  const map = (unwrapToolData(raw) as Record<string, unknown> | null)?.[key];
  return map && typeof map === "object" ? Object.keys(map) : [];
};
export async function listProfiles(): Promise<string[]> { return names(await callTool("sandbox_list_profiles"), "profiles"); }
export async function listDevicePresets(): Promise<string[]> { return names(await callTool("sandbox_list_device_presets"), "presets"); }

/** Only what the person chose is sent; an empty object asks for the default environment. */
export async function provision(choice: { profile?: string; device_preset?: string }): Promise<void> {
  unwrapToolData(await callTool("sandbox_provision", { ...choice }));
}
export async function terminate(envId: string): Promise<void> {
  unwrapToolData(await callTool("sandbox_terminate", { env_id: envId }));
}

/** Provisioning fails with one opaque code for several causes; do not guess which. */
export function sandboxFailure(prose: string, cause: unknown): string {
  const reason = errorReason(cause) ?? "";
  if (/tool_execution_failed/.test(reason)) return "The environment could not be provisioned. The chosen profile or device preset may not be available; the server log has the details.";
  return withReason(prose, reason || undefined);
}
